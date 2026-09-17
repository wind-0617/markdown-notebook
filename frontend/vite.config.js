import { defineConfig } from "vite";

// 开发代理：前端 5173 → 后端 API（指令文档·六）。
// 后端端口可用 PORT 环境变量覆盖，与 run 脚本保持一致。
const backend = `http://127.0.0.1:${process.env.PORT || 5000}`;

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 4200, // monaco 体积固定项，勿因此报警
  },
});
