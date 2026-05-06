import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** 仅路径型前缀走 dev/preview 代理；完整 http(s) URL 时不配置代理（由浏览器直连，需后端 CORS） */
function buildApiProxy(mode: string) {
  const env = loadEnv(mode, __dirname, "");
  const raw = (env.VITE_API_PREFIX || "/api").trim().replace(/\/$/, "") || "/api";
  if (/^https?:\/\//i.test(raw)) {
    return {};
  }
  const p = raw.startsWith("/") ? raw : `/${raw}`;
  return {
    [p]: {
      target: "http://127.0.0.1:8000",
      changeOrigin: true,
      rewrite: (reqPath: string) => reqPath.replace(new RegExp(`^${escapeRegExp(p)}`), ""),
    },
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: buildApiProxy(mode),
  },
  preview: {
    proxy: buildApiProxy(mode),
  },
}));
