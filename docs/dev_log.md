# 开发日志（dev log）

> 按 `AI_INSTRUCTIONS.txt` 要求维护：**每完成一个功能追加一条记录**，倒序不重要，
> 按时序累积即可。格式：`## [日期] 标题` + 问题描述 / 原因分析 / 解决方案 / 涉及文件 / 备注。

---

## [2026-09-10] 项目历史回溯（v0.1 → v1.0.0）

- **v0.1 框架**：按《开发文档》搭 Flask + subprocess 执行引擎（`-I -E -B` 隔离参数）、
  @param DSL 解析、Markdown 渲染、笔记 CRUD、Docker 一次性沙箱模式。
- **v0.2 体验**：按《优化文档》做主题系统（CSS 变量深浅色）、三段布局、侧栏双页签、
  AI 设置弹窗、自动保存、运行状态反馈；并调研 idea-note / mrmd / flask-jupyter 三个
  开源仓库沉淀《开源项目学习笔记》（flask-jupyter 章节按仓库实况重写，含
  `-I ≠ -E`、常驻内核 P0 规划等结论）。
- **启动脚本**：run.ps1 / run.cmd / run.sh 三平台一键启动（venv→.deps 回退、marker
  防重复安装、就绪轮询）。踩坑：PowerShell 5.1 读**无 BOM** UTF-8 脚本时中文注释
  错乱导致假性语法错误 → 保存为带 BOM 的 UTF-8 解决。
- **v1.0.0 打包上传**：PyInstaller onefile（console、datas=frontend 离线镜像、
  Whoosh 式动态导入用 hiddenimports 补全）、build.bat、GitHub Actions 自动 Release、
  无头冒烟。踩坑：打包版 `sys.executable` 是 exe 自身导致 Python 块自递归 →
  新增解释器探测（`NB_PYTHON` → PATH，排除 exe/_MEIPASS）。E2E 中发现并修复
  note_service 回显未清洗文件名的真实 bug（`"../evil.md"` 响应说谎 → `_safe_path`
  返回真实名）。随后完成 GitHub 初始化上传（推送前秘密扫描 48 文件无泄漏；
  作者改用 noreply 邮箱；远端占位 README 提交用 `--force-with-lease` 清除）。
- **涉及文件**：全仓库。
- **备注**：该阶段前端为 CDN 资产 + 后端占位符重写（`__ASSET_BASE__` + vendor 镜像），
  已在 v0.3 被 Vite 方案整体替代。

---

## [2026-09-17] v0.3 前后端分离（Vite + Flask 纯 API + 统一信封）

- **问题描述**：按《AI_INSTRUCTIONS.txt》把项目升级为前后端分离架构：后端原
  `app.py` 单文件里混着页面路由、CDN 占位符重写与全部 API；响应形状五花八门
  （有的顶层字段、有的 `{error}` 字符串），前端各模块手写 fetch + 硬编码 URL。
- **原因分析**：v0.1/v0.2 快速迭代遗留。指令文档要求 routes/ 蓝图、统一
  `{success,data,error:{code,message}}` 信封、src/api/ 封装层。
- **解决方案**：
  1. 后端拆为 `routes/`（system/render/execute/notes/search/ai/git 七个蓝图）+
     `deps.py` 服务单例 + `api_response.py`（ok/fail + 稳定错误码表：
     BAD_REQUEST / NOT_FOUND / NOTE_NAME_INVALID / NOTE_EXISTS / LANGUAGE_UNSUPPORTED /
     ENVIRONMENT_UNAVAILABLE / AI_NOT_CONFIGURED / AI_UPSTREAM_ERROR / GIT_ERROR /
     SEARCH_ERROR / INTERNAL）；404/500 全局兜底也走信封。
  2. `app.py` 只剩：建应用、挂蓝图、CORS（仅当设了 `CORS_ORIGINS` 白名单，禁止 `*`）、
     错误处理器与启动入口。
  3. **exe 双形态兼容**：文档设想的 Nginx 托管 dist 与"双击 exe 即用"冲突，
     故保留一个例外——Flask 纯静态托管 `frontend/dist`（不做任何页面渲染）；
     未构建时 `GET /` 返回带 `npm run build` 指引的信封 404。
  4. 前端重写为 Vite 工程：`src/api/client.js` 统一解析信封并抛 `ApiError`
     （code/message/details），资源模块 notes/execute/search/ai/environment 全部
     基于它；`VITE_API_BASE_URL` 缺省走同源/Vite 代理（`/api → 127.0.0.1:5000`）。
- **涉及文件**：`backend/app.py`、`backend/api_response.py`(新)、`backend/deps.py`(新)、
  `backend/routes/*`(新)、`backend/config.py`、`frontend/**`。
- **备注**：有意偏离文档两处——保留自研 CSS 变量主题（不引 Tailwind，v0.2 设计
  系统已成型）、用原生 ES Modules 而非 Vue（文档允许"Vue 或原生"）；开发日志
  文件名按文档取 `docs/dev_log.md`。

## [2026-09-17] v0.3 Whoosh 全文搜索（中文分词踩坑实录）

- **问题描述**：新增长文检索：文件名/一级标题/正文全覆盖、关键词高亮、保存自动
  更新索引、点击结果直达笔记。实测中索引一写就炸：先后遇到
  `cannot import name 'Lowercase'`、`Analyzer() takes no arguments`、
  `__call__() got an unexpected keyword argument 'mode'/'positions'`、
  `'Token' object has no attribute 'pos'`、`'Hit' object has no attribute 'doc'`、
  `module 'whoosh.highlight' has no attribute 'uformat'` 六连击。
- **原因分析**：Whoosh 2.7.4 的分析器协议细节：①`Analyzer` 不是自定义分词器的
  包装方式（它自己的构造签名是 charset/format 那套）；②字段索引写入会以
  `(value, mode=…, positions=…, boosts=…)` 关键字调用分析器，POSITIONS 格式还要
  读取 **`token.pos`**（词序，非 startpos）——自定义 Tokenizer 必须适配该协议；
  ③查询结果 `Hit` 用下标访问而非 `.doc`；④2.7 的 highlight 模块没有 uformat 函数。
  另外 Whoosh 自带分词对 CJK **整段不切**，中文查询完全不可用。
- **解决方案**：
  1. `CjkBigramTokenizer(Tokenizer)`：CJK 连续段产 **unigram+bigram** 双流
     （单字兜底、双字精准），拉丁/数字按词并内置小写；实现 `reset()`、
     `__call__(value, mode, positions, keeplist, **kw)` 兼容 Whoosh 调用协议，
     每个 token 赋 `mode="word"`、`pos`（自增词序）。
  2. 查询 `MultifieldParser(["title","content","name"], group=OrGroup)` 宽松召回，
     `sortedby="modified"` 倒序；结果 `hit["name"]` 下标取。
  3. 高亮弃用 whoosh.highlight，自写 `_snippet()`：定位首命中词 → 取窗口 →
     **先转义再单遍正则替换**（长词优先，避免 `<u>` 嵌套），只产 `<u>` 标签，
     前端可直接注入（已 smoke 断言）。
  4. 集成层：`SearchService.index_note/remove_note/rebuild`，note_routes 写操作
     后同步索引（失败仅打印，绝不影响笔记主流程）；索引目录缺失时首次查询自动
     全量重建；重入死锁修正（先 `_open()` 后取写锁）。
  5. 配置：`SEARCH_INDEX_DIR`（dev=backend/.search_index，frozen=exe 同级）；
     `.gitignore` 新增；requirements 加 `Whoosh>=2.7`。
- **涉及文件**：`backend/services/search_service.py`(新)、`backend/routes/search_routes.py`(新)、
  `backend/routes/note_routes.py`、`backend/config.py`、`requirements.txt`、`.gitignore`。
- **备注**：smoke 用例含中文词（鹈鹕）命中、`<u>` 高亮断言、删除后不再命中、
  重建计数。索引体积换召回率（unigram+bigram 双写），个人笔记量级完全够用。

## [2026-09-17] v0.3 Java/Go 执行器与环境探测

- **问题描述**：按文档补 Java、Go 两种语言的执行，并要求"未安装时给出安装引导"
  而不是裸抛 FileNotFoundError；同时 /api/execute 要在环境缺失时短路返回。
- **原因分析**：BaseExecutor 已有超时/临时目录/Docker 包装，缺的只是命令构造与
  探测层；Java 版本判定特殊——**单文件源码启动 `java Main.java` 需要 JDK 11+**，
  仅探测 `java` 存在不够（老 8 会失败）。
- **解决方案**：
  1. `JavaExecutor`（`java Main.java`，`.java`）与 `GoExecutor`（`go run main.go`，
     `.go`）；`executors/__init__` 导入即注册；`param_parser._COMMENT_PREFIX`
     增加 java/go 的 `//`（@param 行剥离对五语言统一）。
  2. `services/environment.py`：五语言探测（`-V/--version/go version`，5~6s 超时，
     60s 缓存；不可用结果不缓存以便装完即恢复）；Java 解析版本号并强制 ≥11；
     Python 复用 `resolve_interpreter_path()`（由私有转正）。
  3. `/api/environment/check?lang=` + `/api/health.languages[]`；execute 路由
     预检失败返回 `ENVIRONMENT_UNAVAILABLE`(424) + hint，前端 Toast 显示引导。
  4. **参数控件边界**：java/go 单文件模式没有合法的"文件头注入赋值"语法位
     （Java 顶层不能有语句、Go 需 `:=` 且 import 位置敏感），与其静默出错，
     execute 对这两语言传非空 params 明确 400，前端也不渲染控件——文档口径
     统一写进 API 文档与 README。
- **涉及文件**：`backend/executors/java_executor.py`(新)、`go_executor.py`(新)、
  `executors/__init__.py`、`executors/python_executor.py`、`parsers/param_parser.py`、
  `backend/services/environment.py`(新)、`routes/execute_routes.py`、`routes/system_routes.py`。
- **备注**：本机未装 JDK/Go，冒烟只断言探测形状与降级；exe E2E 同样跳过执行链。

## [2026-09-17] v0.3 前端 Vite 组件化与界面优化

- **问题描述**：旧前端是 7 个 `window.App` IIFE + CDN 脚本（Monaco loader、
  marked、hljs），离线化靠后端重写占位符；缺搜索页签、Toast、Ctrl+K。
- **原因分析**：v0.2 遗留结构，与分离架构不匹配。
- **解决方案**：
  1. Vite 工程：npm 直依赖 `monaco-editor@0.45.0 / marked@12 / highlight.js@11.9`；
     Monaco 用 `editor.worker?worker` 替代跨域 blob 技巧；hljs 双主题 CSS 经
     `?url` 导入，主题切换改 `<link id="hljs-theme">`；**App.js 动态
     `import("./Editor.js")` 把 3.1MB 的 Monaco 切成懒加载分片**，首屏 index
     chunk 仅 226KB。
  2. 组件化移植（逻辑与 v0.2 行为一一对应）：Editor/Controls/Preview/Executor/
     Sidebar/SearchPanel/AIPanel/StatusBar/Toast + App 装配层；
     `state.js` 单一事实源；`utils/misc.js`（debounce/escapeHtml/codeHash/fmtTime）、
     `utils/shortcuts.js`（全局 Ctrl+S / Ctrl+K）。
  3. 新增界面项：🔍 搜索页签（300ms 防抖、过期响应 seq 丢弃、结果 `<u>` 高亮 +
     相对时间、点击直达打开、🔄 重建索引）、全局 Toast（错误不 alert 不阻塞）、
     侧栏整体折叠（btn-sidebar + localStorage 偏好 + <860px 默认收起）、
     状态栏语言环境灯（🐍📦💲☕🐹 + title 里放版本/安装 hint）、主要交互控件
     补 aria-label。
  4. 样式迁移脚本化：`css/style.css` 按节注释边界无损拆成
     `src/styles/main.css + markdown.css`（自检"丢失行数 0"），v0.3 新样式追加。
  5. 旧 CDN/占位符体系整体退役：删 `frontend/js|css|vendor`、`tools/fetch_assets.py`；
     spec datas 改 `frontend/dist → frontend`；build.bat/CI/run 脚本加 npm 步骤；
     CI 冒烟升级（npm ci → 构建 → exe → 信封断言 + Vite 产物引用断言 +
     中文检索链路断言）。
- **涉及文件**：`frontend/**`（全新）、`markdown-notebook.spec`、`build.bat`、
  `.github/workflows/release.yml`、`run.ps1`、`run.sh`。
- **备注**：run.ps1 编辑后 BOM 被工具剥掉，PS5.1 会再次乱码——已重新写入 BOM 并用
  PSParser 验证 0 语法错误。`npm run dev` 在 Node 24 下监听 `localhost`（可能仅
  ::1），验证脚本要用 `http://localhost:5173` 而非 127.0.0.1。

## [2026-09-17] v0.3 验证结果

- `_selftest.py`（执行器/参数层）：SELFTEST OK。
- `_smoke.py` 重写为信封断言版，11 项：health / execute / bad-language /
  param-execute / render+parse / environment / **search(whoosh)** / notes-crud /
  path-guard / static-hosting（dist 有则验 `/assets/`，无则验指引文案）/
  ai-degrade → **SMOKE OK**。
- HTTP 层实测：5000（Flask 托管 dist：入口 JS/CSS 哈希资源 200）与 5173
  （Vite 代理 /api）双链路全通；搜索"示例"命中示例笔记。
- exe 重建 E2E（dist/markdown-notebook.exe @5111）：**22/22 ALL OK**——信封、
  五语言注册、Vite 产物静态托管、python/java 真实执行链、中文检索全链路
  （建笔记→命中→`<u>` 高亮→删除→索引同步）、exe 同级 `.search_index\` 与
  `notebooks\` 落地、424 环境引导、go params 拒绝。发布 zip 15.7MB（比 v1.0.0
  的 16.7MB 更小：vendor 镜像体系退役）。
- **E2E 中揪出的真实 bug**：Java 探测正则失配——JDK 9+ 的 `java --version`
  首行是 `java 21.0.6 …`（不再含 "version" 字样），旧正则只认
  `version "N"`，把本机 JDK 21 误判为"环境不可用"。修复为
  `version\s+"?(\d+)` 与 `^(openjdk|java)\s+(\d+)` 双模式（1.x 老版一律判不可用，
  因单文件源码启动需 ≥11）。修复后 exe 内 java 块真实执行输出 42。
  教训：环境探测必须以输出文本为准，验收脚本对"存根/半可用"环境要接受
  424 拦截与执行成功两种合法结局。
