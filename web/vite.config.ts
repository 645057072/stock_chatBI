import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** 与 Docker Nginx 一致：浏览器请求 /api/*，转发到后端根路径（FastAPI 路由为 /auth、/chat 等） */
const apiProxy = {
  "/api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, ""),
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { ...apiProxy },
  },
  // preview 不继承 server.proxy；本地 preview / 自定义端口（如 8881）无此项时 /api 会 404
  preview: {
    proxy: { ...apiProxy },
  },
});
