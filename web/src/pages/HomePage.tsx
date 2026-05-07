import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiLogin, apiMe, apiRegister, NETWORK_UNAVAILABLE_ZH } from "../api";
import styles from "./HomePage.module.css";

export default function HomePage() {
  const nav = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const me = await apiMe();
        if (cancelled) return;
        if (me) nav("/chat");
      } catch (ex) {
        if (cancelled) return;
        const msg = ex instanceof Error ? ex.message : NETWORK_UNAVAILABLE_ZH;
        setErr(msg);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [nav]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      if (mode === "register") {
        await apiRegister(username.trim(), password);
        await apiLogin(username.trim(), password);
      } else {
        await apiLogin(username.trim(), password);
      }
      nav("/chat");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <h1 className={styles.title}>ChatBI 股票助手</h1>
        <p className={styles.sub}>基于历史行情与智能问答，请先注册或登录。</p>

        <div className={styles.tabs}>
          <button
            type="button"
            className={mode === "login" ? styles.tabOn : styles.tab}
            onClick={() => setMode("login")}
          >
            登录
          </button>
          <button
            type="button"
            className={mode === "register" ? styles.tabOn : styles.tab}
            onClick={() => setMode("register")}
          >
            注册
          </button>
        </div>

        <form className={styles.form} onSubmit={onSubmit}>
          <label className={styles.label}>
            用户名
            <input
              className={styles.input}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              minLength={3}
            />
          </label>
          <label className={styles.label}>
            密码
            <input
              className={styles.input}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              required
              minLength={mode === "register" ? 8 : 1}
            />
          </label>
          {err ? <p className={styles.err}>{err}</p> : null}
          <button className={styles.submit} type="submit" disabled={loading}>
            {loading ? "处理中…" : mode === "register" ? "注册并进入" : "登录"}
          </button>
        </form>
      </div>
    </div>
  );
}
