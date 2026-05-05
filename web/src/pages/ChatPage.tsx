import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  apiChat,
  apiChatHistory,
  apiClearChat,
  apiLogout,
  apiMe,
  ChatMessage,
} from "../api";
import styles from "./ChatPage.module.css";

type Row = { role: "user" | "assistant"; text: string };

function toRows(messages: ChatMessage[]): Row[] {
  const out: Row[] = [];
  for (const m of messages) {
    if (m.role !== "user" && m.role !== "assistant") continue;
    const c = m.content;
    if (typeof c !== "string") continue;
    out.push({ role: m.role, text: c });
  }
  return out;
}

export default function ChatPage() {
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void (async () => {
      const me = await apiMe();
      if (!me) {
        nav("/");
        return;
      }
      setUsername(me.username);
      const hist = await apiChatHistory();
      setRows(toRows(hist));
    })();
  }, [nav]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [rows, sending]);

  async function onLogout() {
    await apiLogout();
    nav("/");
  }

  async function onNewChat() {
    setErr(null);
    try {
      await apiClearChat();
      setRows([]);
    } catch {
      setErr("清空会话失败");
    }
  }

  async function onSend(e?: FormEvent | KeyboardEvent) {
    e?.preventDefault();
    const q = input.trim();
    if (!q || sending) return;
    setInput("");
    setErr(null);
    setRows((r) => [...r, { role: "user", text: q }]);
    setSending(true);
    try {
      const { reply } = await apiChat(q);
      setRows((r) => [...r, { role: "assistant", text: reply }]);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "发送失败");
      setRows((r) => r.slice(0, -1));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>ChatBI</div>
        <button type="button" className={styles.sideBtn} onClick={onNewChat}>
          新对话
        </button>
        <div className={styles.sideHint}>股票查询助手</div>
        <div className={styles.spacer} />
        <div className={styles.userBox}>
          <div className={styles.userName}>{username || "…"}</div>
          <button type="button" className={styles.linkBtn} onClick={onLogout}>
            退出登录
          </button>
        </div>
      </aside>

      <div className={styles.centerWrap}>
      <main className={styles.main}>
        <header className={styles.header}>
          <span className={styles.headerTitle}>股票查询对话</span>
        </header>

        <div className={styles.feed}>
          {rows.length === 0 ? (
            <p className={styles.placeholder}>输入问题开始查询，例如贵州茅台近一年收盘价走势。</p>
          ) : null}
          {rows.map((row, i) =>
            row.role === "user" ? (
              <div key={i} className={styles.rowUser}>
                <div className={styles.bubbleUser}>{row.text}</div>
              </div>
            ) : (
              <div key={i} className={styles.rowBot}>
                <div className={styles.avatar} />
                <div className={styles.bubbleBot}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{row.text}</ReactMarkdown>
                </div>
              </div>
            )
          )}
          {sending ? <div className={styles.thinking}>助手思考中…</div> : null}
          {err ? <div className={styles.feedErr}>{err}</div> : null}
          <div ref={bottomRef} />
        </div>

        <footer className={styles.footer}>
          <form className={styles.inputBar} onSubmit={onSend}>
            <button type="button" className={styles.attach} title="附件占位" disabled>
              +
            </button>
            <textarea
              className={styles.textarea}
              rows={1}
              value={input}
              placeholder="输入股票相关问题…"
              onChange={(e) => setInput(e.target.value)}
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
          <li>
            <strong>本地行情库</strong>
            <span>MySQL「stock_daily」存储 A 股日线；助手优先查库作答。</span>
          </li>
          <li>
            <strong>联网补数</strong>
            <span>库中无数据时，通过 Tushare 拉取日线并写入数据库（需在服务端配置 TUSHARE_TOKEN）。</span>
          </li>
          <li>
            <strong>SQL 与图表</strong>
            <span>自然语言转 SQL、查询结果表格与自动走势图。</span>
          </li>
          <li>
            <strong>ARIMA 预测</strong>
            <span>基于近一年收盘价预测未来若干交易日（工具：arima_stock）。</span>
          </li>
          <li>
            <strong>布林带</strong>
            <span>20 日、2σ 超买超卖触点检测（工具：boll_detection）。</span>
          </li>
          <li>
            <strong>Prophet</strong>
            <span>趋势与季节性分解可视化（工具：prophet_analysis）。</span>
          </li>
          <li>
            <strong>大模型</strong>
            <span>通义千问编排工具调用；API Key：DASHSCOPE_API_KEY。</span>
          </li>
        </ul>
      </aside>
      </div>
    </div>
  );
}
