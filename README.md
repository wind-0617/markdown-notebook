# 📓 Markdown 可执行笔记工具（markdown-notebook）

> 边写边跑的 Markdown 笔记：既有 Markdown 的简洁写作体验，又能像 Jupyter 一样
> 直接运行代码块——**文档即程序**。

## ✨ 核心功能

| 阶段 | 功能 |
|------|------|
| **MVP** | Monaco 编辑 · 实时预览 · `Shift+Enter` 运行 Python 代码块 · 笔记 CRUD · 语法高亮 |
| **交互增强** | 代码块内 `# @param` 声明滑块/下拉框 · 调参自动重跑 · JS/Shell 执行 · 结果内联保存 |
| **智能增强** | AI 助手（⚙️ 浏览器内配置，问答/总结/生成）· Git 同步 · 文件树 · 加密 |
| **体验 v0.2** | 深色/浅色主题 · 双页签侧栏 · 三段布局切换 · 自动保存 · 运行状态反馈 · 安全提示 |
| **架构 v0.3** | **前后端分离**（Vite + Flask 纯 API）· **Whoosh 全文搜索**（中文分词+高亮）· **Java/Go 执行** + 环境探测安装引导 · 统一响应信封 · Toast / Ctrl+K |

## 🧱 技术栈

- **后端**：Flask 蓝图（`routes/`）+ subprocess/Docker 沙箱 + Whoosh 检索，只做 JSON
- **前端**：**Vite + 原生 ES Modules** + npm 依赖（Monaco / marked / highlight.js），组件化 `src/{api,components,styles,utils}`
- **主题**：自定义 CSS 变量设计系统，深色/浅色一键切换（偏好持久化）
- **AI**：任意 OpenAI 兼容端点（DeepSeek / GPT / Ollama），浏览器端 ⚙️ 配置
- **执行语言**：Python / JavaScript / Shell / Java（JDK 11+ 单文件）/ Go
- **存储**：标准 `.md` 文件 + 本地 Whoosh 索引目录，随时迁移

## 🚀 快速开始

### 方式 A：一键启动（推荐，全栈）

| 系统 | 命令 |
|------|------|
| **Windows** | 双击 `run.cmd`，或 PowerShell 执行 `.\run.ps1`（首次被拦截时：`powershell -ExecutionPolicy Bypass -File run.ps1`） |
| **macOS / Linux** | `chmod +x run.sh && ./run.sh` |

脚本自动完成：创建 venv（失败自动回退 `backend/.deps`）→ 装 Python 依赖 →
**构建前端**（`npm install + npm run build` → `frontend/dist`，已有产物则跳过）→
启动 Flask → 轮询就绪 → 打开浏览器 `http://127.0.0.1:5000`。
`Ctrl+C` 停止；`run.ps1 -Reinstall` 强制重装、`run.ps1 -Stop` 停止服务。

### 方式 B：分离开发（前端热更新）

```bash
# 终端 1：后端（纯 API）
cd backend && python app.py            # :5000

# 终端 2：前端 dev server（/api 自动代理到 5000）
cd frontend && npm install && npm run dev   # 访问 :5173
```

改前端代码即时热更新；改后端无需重启构建。发布时 `npm run build` 出静态产物。

> 纯手动跑后端而未构建前端时，`GET /` 会返回带 `npm run build` 指引的 JSON——
> 这是设计行为（后端不渲染页面）。

### Docker 生产部署（沙箱执行）

```bash
docker build -t markdown-notebook-sandbox:latest docker/
cd docker && docker compose up --build
```

## ⌨️ 快捷键

| 按键 | 动作 |
|------|------|
| `Shift+Enter` | 执行光标所在（或其后最近）代码块 |
| `Ctrl+S` | 保存到 `backend/notebooks/` |
| `Ctrl+K` | 跳到 🔍 搜索页签并聚焦输入框 |

## 🔍 全文搜索

Whoosh 索引 **文件名 + 一级标题 + 正文（含代码）**，中文按双字滑窗切分，
结果带 `<u>` 高亮片段与修改时间，点击直达笔记；保存/新建/删除自动同步索引，
🔄 按钮可全量重建（索引在 `backend/.search_index/`，可删可重建，勿提交）。

## 🧪 交互参数示例

````markdown
```python
# @param n 样本量 slider min=10 max=1000 step=10 default=100
# @param sep 分隔符 text default=-
import random
data = [random.randint(0, 100) for _ in range(int(n))]
print(sep.join(str(x) for x in data[:20]))
```
````

> 参数控件支持 python / javascript / shell；Java/Go 块请直接写在代码里。
> Java 公共类须命名 `Main`；Go 须有 `func main()`。缺环境时运行会收到
> 一键可复制的安装引导（424 + hint）。

## 📁 目录结构

```
├── backend/
│   ├── app.py            Flask 入口（纯 API + dist 静态托管例外）
│   ├── api_response.py   统一信封 ok()/fail() + 错误码表
│   ├── deps.py           服务单例
│   ├── routes/           蓝图：system/render/execute/notes/search/ai/git
│   ├── executors/        python/js/shell/java/go + local/docker 双模式
│   ├── parsers/          markdown / @param DSL
│   └── services/         note / ai / git / search(Whoosh) / environment
├── frontend/             Vite 工程（npm）
│   ├── index.html        SPA 骨架
│   ├── vite.config.js    /api 代理 → :5000
│   └── src/
│       ├── api/          client(信封解析)+notes/execute/search/ai/environment
│       ├── components/   App/Editor/Preview/Controls/Executor/Sidebar/
│       │                 SearchPanel/AIPanel/StatusBar/Toast
│       ├── styles/       main.css + markdown.css
│       └── utils/        misc / shortcuts
├── docker/  docs/  packaging/  tools/
└── run.ps1 / run.sh / run.cmd / build.bat / markdown-notebook.spec
```

## 📦 打包发布（Windows exe）

免安装单文件版：**Vite 构建前端** → PyInstaller 把 Flask + `frontend/dist`
打成一个 `markdown-notebook.exe`，双击启动服务并自动打开浏览器（完全离线可用）。

```bash
# 本地构建（Windows）：venv 检查 → 依赖 → npm build → PyInstaller → zip
build.bat

# 正式发布：推 tag 触发 GitHub Actions（setup-node + Vite 构建 + exe + 无头冒烟 + Release）
git tag v1.1.0 && git push origin v1.1.0
```

产物 `dist/markdown-notebook-windows-x64.zip` = exe + 使用说明.txt + notebooks/示例笔记.md。
笔记数据与搜索索引**不进 exe**（存于 exe 同级目录，升级只换 exe，数据不丢）。
exe 不含解释器：运行代码块需本机装对应语言环境（状态栏有语言灯 + 安装引导），或用 Docker 模式。

| 文件 | 作用 |
|------|------|
| `markdown-notebook.spec` | PyInstaller 配置（datas 打包 `frontend/dist`、Whoosh 反射子模块全收集） |
| `build.bat` | 本地一键构建（含 npm 步骤） |
| `tools/package_dist.py` | 组装发布 zip |
| `.github/workflows/release.yml` | tag 触发自动构建发布 |

## 🛡️ 安全说明

- 开发模式（`EXECUTOR_MODE=local`）用本机 subprocess，仅供个人使用；
- 生产模式（`EXECUTOR_MODE=docker`）在断网、只读、内存/CPU 限额的一次性容器中执行；
- 笔记文件名白名单校验禁止路径穿越；执行超时可配置（默认 30s，上限 120s）；
- CORS 默认关闭（同源）；跨域分离部署时设 `CORS_ORIGINS` 白名单，**不要用 `*`**。

## 📖 文档

- [需求分析](docs/需求分析.md) ｜ [项目规划](docs/项目规划.md)
- [开发手册](docs/开发手册.md) ｜ [API 文档](docs/API文档.md) ｜ [开发日志](docs/dev_log.md)
- [开源项目学习笔记](docs/开源项目学习笔记.md)（idea-note / mrmd / flask-jupyter 调研与移植清单）

## 🤝 贡献指南

1. 阅读 `docs/开发手册.md`，按阶段认领任务；
2. 新建分支 `feature/fr-xx-简述`，PR 描述关联 FR 编号；
3. **每完成一个功能在 `docs/dev_log.md` 追加一条记录**（问题/原因/方案/涉及文件）；
4. API/结构变更同步更新 `docs/API文档.md`。

## 许可证

MIT License（占位，正式发布前确认）
