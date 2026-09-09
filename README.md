# 📓 Markdown 可执行笔记工具（markdown-notebook）

> 边写边跑的 Markdown 笔记：既有 Markdown 的简洁写作体验，又能像 Jupyter 一样
> 直接运行代码块——**文档即程序**。

## ✨ 核心功能

| 阶段 | 功能 |
|------|------|
| **MVP** | Monaco 编辑 · 实时预览 · `Shift+Enter` 运行 Python 代码块 · 笔记 CRUD · 语法高亮 |
| **交互增强** | 代码块内 `# @param` 声明滑块/下拉框 · 调参自动重跑 · JS/Shell 执行 · 结果内联保存 |
| **智能增强** | AI 助手（⚙️ 浏览器内配置，问答/总结/生成）· Git 同步 · 文件树 · 加密 |
| **体验 v0.2** | 深色/浅色主题 · 笔记/AI 双页签侧栏 · 三段布局切换 · 自动保存 · 运行状态反馈 · 安全提示 |

## 🧱 技术栈

- **后端**：Flask + subprocess/Docker 沙箱
- **前端**：原生 HTML/CSS/JS + Monaco Editor + marked
- **主题**：自定义 CSS 变量设计系统，深色/浅色一键切换（偏好持久化）
- **AI**：任意 OpenAI 兼容端点（DeepSeek / GPT / Ollama），浏览器端 ⚙️ 配置
- **存储**：标准 `.md` 文件，随时迁移

## 🚀 快速开始

### 一键启动（推荐）

| 系统 | 命令 |
|------|------|
| **Windows** | 双击 `run.cmd`，或 PowerShell 执行 `.\run.ps1`（首次被拦截时：`powershell -ExecutionPolicy Bypass -File run.ps1`） |
| **macOS / Linux** | `chmod +x run.sh && ./run.sh` |

脚本自动完成：创建 venv（失败自动回退 `backend/.deps`）→ 安装依赖（marker 防重复）→
启动 Flask → 轮询就绪 → 打开浏览器 `http://127.0.0.1:5000`。`Ctrl+C` 停止；
`run.ps1 -Reinstall` 强制重装、`run.ps1 -Stop` 停止服务、`NO_BROWSER=1 ./run.sh` 不开浏览器。

### 手动启动

```bash
# 1. 安装依赖（Python 3.10+）
cd backend
pip install -r requirements.txt

# 2. 启动
python app.py

# 3. 浏览器打开 http://127.0.0.1:5000
```

第一次打开即可体验：把光标放进预览区的代码块，按 **Shift+Enter** 运行；
拖动滑块参数会自动重新执行（需联网加载 Monaco CDN；界面自带深浅色主题与自动保存）。

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

## 📁 目录结构

```
├── backend/     Flask API + 执行引擎(executors) + 解析器(parsers) + 服务(services)
├── frontend/    index.html + css/ + js/（Monaco、预览、执行、控件、AI 面板）
├── docker/      沙箱镜像与 compose 编排
├── docs/        需求分析 / 项目规划 / 开发手册 / API 文档
└── README.md
```

## 📦 打包发布（Windows exe）

免安装单文件版：PyInstaller 将 Flask 服务 + 前端（含 **Monaco/marked/hljs 离线镜像**）
打成一个 `markdown-notebook.exe`，双击启动服务并自动打开浏览器。

```bash
# 本地构建（Windows）：venv 检查 → 依赖 → 资产镜像 → PyInstaller → zip，一键四步
build.bat

# 正式发布：推 tag 触发 GitHub Actions（windows runner 构建 + 无头冒烟测试 + 传 Release）
git tag v1.0.0 && git push origin v1.0.0
```

产物 `dist/markdown-notebook-windows-x64.zip` = exe + 使用说明.txt + notebooks/示例笔记.md。
笔记数据**不进 exe**（存于 exe 同级 `notebooks\`，升级只换 exe，数据不丢）。
exe 不含 Python 解释器（省 ~40MB）：运行 Python 块需本机 Python、或设 `NB_PYTHON`、或 Docker 模式。

| 文件 | 作用 |
|------|------|
| `markdown-notebook.spec` | PyInstaller 配置（datas 打包 frontend/、hiddenimports 补动态导入） |
| `build.bat` | 本地一键构建 |
| `tools/fetch_assets.py` | CDN 依赖 → `frontend/vendor/` 离线镜像 |
| `tools/package_dist.py` | 组装发布 zip |
| `.github/workflows/release.yml` | tag 触发自动构建发布 |

## 🛡️ 安全说明

- 开发模式（`EXECUTOR_MODE=local`）用本机 subprocess，仅供个人使用；
- 生产模式（`EXECUTOR_MODE=docker`）在断网、只读、内存/CPU 限额的一次性容器中执行；
- 笔记文件名做白名单校验，禁止路径穿越；执行超时可配置（默认 30s，上限 120s）。

## 📖 文档

- [需求分析](docs/需求分析.md) ｜ [项目规划](docs/项目规划.md)
- [开发手册](docs/开发手册.md) ｜ [API 文档](docs/API文档.md)
- [开源项目学习笔记](docs/开源项目学习笔记.md)（idea-note / mrmd / flask-jupyter 调研与移植清单）

## 🤝 贡献指南

1. 阅读 `docs/开发手册.md`，按阶段认领任务；
2. 新建分支 `feature/fr-xx-简述`，PR 描述关联 FR 编号；
3. API/结构变更同步更新 `docs/API文档.md`。

## 许可证

MIT License（占位，正式发布前确认）
