import { FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  apiChat,
  apiChatHistory,
  apiChatSessions,
  apiChatUndo,
  apiLogout,
  apiMe,
  apiNewChatSession,
  apiSelectChatSession,
  AUTH_EXPIRED_MESSAGE,
  ChatAbortedError,
  ChatMessage,
  ChatSessionMeta,
  NETWORK_UNAVAILABLE_ZH,
  sanitizeAssistantReply,
} from "../api";
import styles from "./ChatPage.module.css";

type Row = { role: "user" | "assistant"; text: string };

/** 不超过 7 条：与右侧服务能力对应的简易查询缓存（点击即发起对话） */
const QUICK_PROMPTS: string[] = [
  "查询贵州茅台近一年收盘价走势",
  "统计平安银行本月日均成交量",
  "用 ARIMA 预测宁德时代未来10个交易日收盘价",
  "检测五粮液近一年布林带20日2σ超买超卖日期",
  "同步 600519.SH 近两年日线后再查最新收盘价",
  "对比贵州茅台与五粮液近三月收盘价",
  "用 Prophet 分析比亚迪近一年 trend 与季节性",
];

function toRows(messages: ChatMessage[]): Row[] {
  const out: Row[] = [];
  for (const m of messages) {
    if (m.role !== "user" && m.role !== "assistant") continue;
    const c = m.content;
    if (typeof c !== "string") continue;
    const text = m.role === "assistant" ? sanitizeAssistantReply(c) : c;
    out.push({ role: m.role, text });
  }
  return out;
}

export default function ChatPage() {
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [sessions, setSessions] = useState<ChatSessionMeta[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  /** 用户一旦开始输入或发送，隐藏中部示例缓存区（与 rows 是否为空解耦，避免失败后缓存重新弹出） */
  const [hideQuickPrompts, setHideQuickPrompts] = useState(false);
  /** 助手请求进行中时已等待秒数（仅展示） */
  const [thinkingSeconds, setThinkingSeconds] = useState(0);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  /** 发送中的对话请求，供「撤销」中止等待（服务端任务仍可能继续直至结束） */
  const chatAbortRef = useRef<AbortController | null>(null);

  const refreshSessions = useCallback(async () => {
    try {
      const data = await apiChatSessions();
      setSessions(data.sessions || []);
      if (data.active_session_id) setActiveSessionId(data.active_session_id);
    } catch {
      /* 忽略列表刷新失败 */
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const me = await apiMe();
        if (!me) {
          nav("/");
          return;
        }
        setUsername(me.username);
        await refreshSessions();
        const hist = await apiChatHistory();
        const initialRows = toRows(hist.messages || []);
        setRows(initialRows);
        setHideQuickPrompts(initialRows.length > 0);
        if (hist.session_id) setActiveSessionId(hist.session_id);
      } catch {
        setErr(NETWORK_UNAVAILABLE_ZH);
      }
    })();
  }, [nav, refreshSessions]);

  // 会话在 Redis 过期或 Cookie 失效后，切回页签时补验，避免仍停在 /chat 却全部接口 401、对话一直转圈
  useEffect(() => {
    const revalidate = () => {
      if (document.visibilityState !== "visible") return;
      void (async () => {
        try {
          const me = await apiMe();
          if (!me) nav("/");
        } catch {
          /* 短暂断网不强制退出，避免误踢回首页 */
        }
      })();
    };
    document.addEventListener("visibilitychange", revalidate);
    window.addEventListener("focus", revalidate);
    return () => {
      document.removeEventListener("visibilitychange", revalidate);
      window.removeEventListener("focus", revalidate);
    };
  }, [nav]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [rows, sending]);

  useEffect(() => {
    if (!sending) {
      setThinkingSeconds(0);
      return;
    }
    const t0 = Date.now();
    setThinkingSeconds(0);
    const id = window.setInterval(() => {
      setThinkingSeconds(Math.floor((Date.now() - t0) / 1000));
    }, 300);
    return () => window.clearInterval(id);
  }, [sending]);

  async function onLogout() {
    await apiLogout();
    nav("/");
  }

  async function onNewChat() {
    setErr(null);
    try {
      const { session_id } = await apiNewChatSession();
      setActiveSessionId(session_id);
      setRows([]);
      setHideQuickPrompts(false);
      await refreshSessions();
    } catch (ex) {
      const msg = ex instanceof Error ? ex.message : "";
      if (msg === AUTH_EXPIRED_MESSAGE) {
        nav("/");
        return;
      }
      setErr("新建会话失败");
    }
  }

  async function onPickSession(id: string) {
    if (id === activeSessionId || sending) return;
    setErr(null);
    try {
      await apiSelectChatSession(id);
      setActiveSessionId(id);
      const hist = await apiChatHistory();
      const nextRows = toRows(hist.messages || []);
      setRows(nextRows);
      setHideQuickPrompts(nextRows.length > 0);
      await refreshSessions();
    } catch (ex) {
      const msg = ex instanceof Error ? ex.message : "";
      if (msg === AUTH_EXPIRED_MESSAGE) {
        nav("/");
        return;
      }
      setErr("切换会话失败");
    }
  }

  async function onUndoFromRow(rowIndex: number) {
    if (sending) {
      // 发送中：仅允许对当前这一条提问撤销等待，不改动此前已完成的问答记录
      if (rowIndex !== rows.length - 1) return;
      chatAbortRef.current?.abort();
      return;
    }
    const row = rows[rowIndex];
    if (!row || row.role !== "user") return;
    setErr(null);
    try {
      const msgs = await apiChatUndo(rowIndex);
      setRows(toRows(msgs));
      await refreshSessions();
    } catch (ex) {
      const msg = ex instanceof Error ? ex.message : "撤销失败";
      setErr(msg);
      if (msg === AUTH_EXPIRED_MESSAGE) nav("/");
    }
  }

  async function onResendFromRow(_rowIndex: number, text: string) {
    if (sending || !text.trim()) return;
    setErr(null);
    await onSend(undefined, text);
  }

  async function onSend(e?: FormEvent | KeyboardEvent, presetText?: string) {
    e?.preventDefault();
    const q = (presetText !== undefined ? presetText : input).trim();
    if (!q || sending) return;
    setHideQuickPrompts(true);
    setInput("");
    setErr(null);
    const ac = new AbortController();
    chatAbortRef.current = ac;
    setRows((r) => [...r, { role: "user", text: q }]);
    setSending(true);
    try {
      const { reply, session_id } = await apiChat(q, activeSessionId || undefined, ac.signal);
      if (session_id) setActiveSessionId(session_id);
      setRows((r) => [...r, { role: "assistant", text: reply }]);
      await refreshSessions();
    } catch (ex) {
      if (ex instanceof ChatAbortedError) {
        try {
          const hist = await apiChatHistory();
          setRows(toRows(hist.messages || []));
          if (hist.session_id) setActiveSessionId(hist.session_id);
          await refreshSessions();
        } catch {
          /* 同步失败时保留本地列表 */
        }
        setErr(null);
      } else {
        const msg = ex instanceof Error ? ex.message : "发送失败";
        setErr(msg);
        if (msg === AUTH_EXPIRED_MESSAGE) {
          nav("/");
        }
      }
    } finally {
      chatAbortRef.current = null;
      setSending(false);
    }
  }

  const showPromptCache =
    !hideQuickPrompts && rows.length === 0 && !input.trim() && !sending;

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>ChatBI</div>
        <button type="button" className={styles.sideBtn} onClick={() => void onNewChat()}>
          新对话
        </button>
        <div className={styles.sessionList} role="list">
          {sessions.map((s) => {
            const id = String(s.id);
            const active = id === activeSessionId;
            return (
              <button
                key={id}
                type="button"
                role="listitem"
                className={active ? styles.sessionItemActive : styles.sessionItem}
                onClick={() => void onPickSession(id)}
                title={s.preview || s.title}
              >
                <span className={styles.sessionTitle}>{s.title || "对话"}</span>
                {s.preview ? <span className={styles.sessionPreview}>{s.preview}</span> : null}
              </button>
            );
          })}
        </div>
        <div className={styles.spacer} />
        <div className={styles.userBox}>
          <div className={styles.userName}>{username || "…"}</div>
          <button type="button" className={styles.linkBtn} onClick={onLogout}>
            退出登录
          </button>
        </div>
      </aside>

      <main className={styles.main}>
        <header className={styles.header}>
          <span className={styles.headerTitle}>股票查询对话</span>
        </header>

        <div className={styles.feed}>
          {showPromptCache ? (
            <div className={styles.promptCache}>
              <p className={styles.promptCacheTitle}>有什么可以帮助你吗？</p>
              <p className={styles.promptCacheHint}>点击下方示例快速提问（不超过 7 条）</p>
              <div className={styles.promptChips}>
                {QUICK_PROMPTS.map((t, i) => (
                  <button
                    key={i}
                    type="button"
                    className={styles.promptChip}
                    disabled={sending}
                    onClick={() => void onSend(undefined, t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {rows.length === 0 && !showPromptCache ? (
            <p className={styles.placeholder}>输入问题开始查询，例如贵州茅台近一年收盘价走势。</p>
          ) : null}
          {rows.map((row, i) =>
            row.role === "user" ? (
              <div key={i} className={styles.rowUser}>
                <div className={styles.userBubbleCol}>
                  <div className={styles.bubbleUser}>{row.text}</div>
                  <div className={styles.userActions} aria-label="用户消息操作">
                    <button
                      type="button"
                      className={styles.msgActionBtn}
                      disabled={sending && i !== rows.length - 1}
                      title={
                        sending && i === rows.length - 1
                          ? "撤销本次咨询：中止等待，不再接收本轮回复（服务端可能仍在处理）"
                          : "从本条提问起删除之后的对话记录"
                      }
                      onClick={() => void onUndoFromRow(i)}
                    >
                      撤销
                    </button>
                    <button
                      type="button"
                      className={styles.msgActionBtn}
                      disabled={sending}
                      title="在当前会话末尾再次发送本条问题，不清空已有问答"
                      onClick={() => void onResendFromRow(i, row.text)}
                    >
                      重发
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div key={i} className={styles.rowBot}>
                <div className={styles.avatar} />
                <div className={styles.bubbleBot}>
                  {row.text.trim() ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{row.text}</ReactMarkdown>
                  ) : (
                    <span className={styles.emptyReply}>（助手未返回正文，请重试或查看服务端日志）</span>
                  )}
                </div>
              </div>
            )
          )}
          {sending ? (
            <div className={styles.thinking} aria-live="polite">
              助手思考中…
              <span className={styles.thinkingTimer}>（已等待 {thinkingSeconds} 秒）</span>
            </div>
          ) : null}
          {err ? <div className={styles.feedErr}>{err}</div> : null}
          <div ref={bottomRef} />
        </div>

        <footer className={styles.footer}>
          <form className={styles.inputBar} onSubmit={(e) => void onSend(e)}>
            <button type="button" className={styles.attach} title="附件占位" disabled>
              +
            </button>
            <textarea
              className={styles.textarea}
              rows={2}
              value={input}
              placeholder="输入股票相关问题…"
              onChange={(e) => {
                const v = e.target.value;
                setInput(v);
                if (v.trim()) setHideQuickPrompts(true);
              }}
              onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void onSend(e);
                }
              }}
            />
            <button type="submit" className={styles.send} disabled={sending}>
              发送
            </button>
          </form>
          <p className={styles.disclaimer}>内容由 AI 生成，请仔细甄别</p>
        </footer>
      </main>

      <aside className={styles.capPanel} aria-label="系统服务能力">
        <div className={styles.capTitle}>服务能力</div>
        <ul className={styles.capList}>
          <li>优先使用已落地的股票日线数据作答，响应更快、结果更稳定。</li>
          <li>本地缺数据或过旧时自动从外部行情源补齐（单只或多只股票均可），再继续回答，无需您手动点同步。</li>
          <li>用口语描述即可生成数据表格，并配上走势类图表便于阅读。</li>
          <li>基于历史价格给出短期走向参考，适合辅助观察节奏。</li>
          <li>从波动区间角度提示阶段性的相对偏高或偏低位置。</li>
          <li>把长期走势拆成趋势与季节性等成分，并用图直观展示。</li>
          <li>理解您的问题并调度上述能力，综合生成分析与说明。</li>
        </ul>
      </aside>
    </div>
  );
}
