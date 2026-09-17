/** 入口：加载样式 → 启动 App（Monaco 由 App.js 内部惰性分片）。 */
import "./styles/main.css";
import "./styles/markdown.css";

import { boot } from "./components/App";

document.addEventListener("DOMContentLoaded", () => {
  boot().catch((err) => {
    console.error(err);
    const tip = document.getElementById("status-tip");
    if (tip) tip.textContent = "初始化失败：" + err.message;
  });
});
