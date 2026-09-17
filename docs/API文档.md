# API 文档（v0.3）

> Base URL：`http://127.0.0.1:5000`（后端只提供 JSON API；页面由 Vite 构建产物静态托管，
> 开发态走 Vite 代理 `5173 → 5000`）。
>
> **v0.3 破坏性变更**：全部响应改为统一信封，旧版裸 JSON 不再兼容。
>
> **v0.3.1 增量（向后兼容）**：新增笔记重命名/导出、AI 连接测试、与笔记绑定的
> 聊天记录读写端点。见 §4、§6。

## 0. 统一响应信封

```jsonc
// 成功
{ "success": true, "data": { ... }, "error": null }
// 失败（HTTP 状态码与语义一致，前端按 error.code 做程序分支）
{ "success": false, "data": null,
  "error": { "code": "NOTE_NAME_INVALID", "message": "文件名不合法：…", "details": { } } }
```

`details` 可选（如不支持语言的候选列表、环境探测结果）。

### 错误码表

| code | 典型 HTTP | 场景 |
|------|-----------|------|
| `BAD_REQUEST` | 400 | 参数缺失/非法、请求体非 JSON |
| `NOT_FOUND` | 404 | 接口不存在、笔记不存在 |
| `NOTE_NAME_INVALID` | 400 | 文件名不符合白名单（中文/字母/数字/空格/`.()-_`，须 `.md` 结尾）；含 `/ \ ..` 一律显式拒绝（不静默净化） |
| `NOTE_EXISTS` | 400 | 新建/重命名时目标笔记已存在 |
| `LANGUAGE_UNSUPPORTED` | 400 | 未注册执行器（`details.languages` 给候选） |
| `ENVIRONMENT_UNAVAILABLE` | 424 | 本机缺解释器（`details.environment.hint` 给安装引导） |
| `AI_NOT_CONFIGURED` | 400 | AI 未配置（前端据此弹设置窗） |
| `AI_UPSTREAM_ERROR` | 502 | AI 上游报错 |
| `GIT_ERROR` | 400 | Git 操作失败/未初始化 |
| `SEARCH_ERROR` | 500 | 索引损坏且重建失败等 |
| `FILE_TOO_LARGE` | 413 | 导出体积超过 10MB 护栏 |
| `NETWORK` | — | 前端封装层：后端未启动/断连 |
| `INTERNAL` | 500 | 兜底内部错误 |

## 1. 系统

### GET /api/health

```json
{ "success": true, "data": {
  "version": "0.3.0", "frozen": false,
  "notebooks_dir": "E:/Markdown-tool/backend/notebooks",
  "frontend_bundled": true,
  "executor_mode": "local",
  "languages": [
    { "language": "java", "registered": true, "available": false,
      "version": null, "hint": "需要 JDK 11+…https://adoptium.net/" },
    { "language": "python", "registered": true, "available": true,
      "version": "Python 3.13.14", "hint": null }
  ],
  "ai_configured": false
}}
```

前端用 `languages` 渲染状态栏"语言环境灯"，`hint` 直接进安装引导。

### GET /api/environment/check?lang=java

单语言探测（服务端 60s 缓存）：

```json
{ "success": true, "data": {
  "language": "java", "available": false, "version": null,
  "hint": "需要 JDK 11+（java 需支持单文件源码启动）：https://adoptium.net/" }}
```

> `available` 对 Java 要求 `java --version` 可解析出 **≥11**（单文件源码启动模式）。

## 2. 渲染与解析

### POST /api/render
请求：`{"markdown": "# hi"}` → `data`：`{"html": "<h1>hi</h1>"}`

### POST /api/parse
提取代码块与交互参数。请求：`{"markdown": "<全文>"}` → `data`：

```json
{ "blocks": [{
  "index": 0, "language": "python", "raw_language": "python",
  "code": "# @param n 数量 slider min=1 max=10 default=3\nprint(n)",
  "start_line": 4, "runnable": true,
  "params": [
    {"name": "n", "label": "数量", "kind": "slider",
     "min": 1, "max": 10, "step": null, "default": 3.0, "options": []}
  ] }]}
```

## 3. 代码执行（FR-03 / FR-08）

### POST /api/execute

| 字段 | 类型 | 说明 |
|------|------|------|
| `language` | string | `python` \| `javascript` \| `shell` \| `java` \| `go`（默认 python） |
| `code` | string | 代码正文（交互参数已展开或另行传 `params`） |
| `params` | object，可选 | `{name: value}`；服务端删 @param 行并注入赋值。**仅 python/javascript/shell**——java/go 传非空 params 返回 `BAD_REQUEST` |
| `timeout` | int，可选 | 1~120 秒，默认取 `EXEC_TIMEOUT`（30） |

成功（执行失败也是 success，用字段区分）：

```json
{ "success": true, "data": {
  "stdout": "42\n", "stderr": "", "exit_code": 0,
  "duration_ms": 213, "timed_out": false, "language": "python", "extra": {} }}
```

环境预检失败：`ENVIRONMENT_UNAVAILABLE`（424），见错误码表。

> Java 代码块：公共类必须命名 `Main`（`java Main.java` 单文件模式）；
> Go 代码块：必须含 `func main()`（`go run main.go`）。

## 4. 笔记管理（FR-05）

| 方法 | 路径 | 说明 | `data` |
|------|------|------|--------|
| GET | `/api/notes` | 列表 | `{"notes":[{name,size,modified}]}` |
| GET | `/api/notes/<name>` | 读取 | `{"name","content"}` |
| POST | `/api/notes` | 新建 `{"name","content"?}` | `{"created":true,"name",…}`（201） |
| PUT | `/api/notes/<name>` | 保存 `{"content"}` | `{"saved":true,"name","size","modified"}` |
| DELETE | `/api/notes/<name>` | 删除 | `{"deleted":true,"name"}` |
| POST | `/api/notes/rename` | 重命名 `{"old_path","new_name"}`（`.md` 可省） | `{"renamed":true,"old_name","name"}` |
| GET | `/api/notes/<name>/export` | 导出下载（**文件流**，非信封） | — 见下 |

响应中的 `name` 为**服务端清洗后的真实文件名**。
**新建/保存/删除/重命名会同步维护搜索索引**（索引故障不影响笔记操作本身）。
**删除会一并清除同名 `.ai-chat.json` 聊天记录；重命名会使其跟随迁移**（见 §6）。

### POST /api/notes/rename（功能一）

`new_name` 校验同新建白名单，且**显式拒绝**含 `/ \ ..` 的输入（不做静默 basename 净化，
避免 `a/b` 被悄悄存成 `b.md` 误导用户）。目标已存在 → `NOTE_EXISTS`；与原名相同 → `BAD_REQUEST`。

### GET /api/notes/<name>/export（功能三）

返回原始 `.md` **字节流**（不做渲染转换，Windows 落盘为 CRLF 原样返回），
`Content-Disposition: attachment`，中文文件名走 RFC 5987（`filename*=UTF-8''…`）。
前端用 `<a href=exportNoteUrl download>` 触发下载，**不经 fetch/信封层**。
体积 > 10MB 返回 `FILE_TOO_LARGE` 信封（413）——故 `<a>` 若命中此分支会跳到错误页，
正常个人笔记远小于该阈值。

## 5. 全文检索（九.3，Whoosh）

### GET /api/search?q=<关键词>

覆盖 **文件名 + 一级标题 + 正文（含代码）**；中文按 unigram+bigram 切分，
英文数字按词；多词自动 OR。`data`：

```json
{ "query": "鹈鹕", "total": 1, "results": [{
    "name": "鸟类.md", "title": "水鸟图鉴",
    "snippet": "# 水鸟图鉴\n\n<u>鹈鹕</u>是一种大型鸟类…",
    "modified": 1789656552, "score": 6.39 }]}
```

`snippet` 为服务端 HTML 安全片段（正文已转义，仅含 `<u>` 高亮标签），前端可直接注入。

### POST /api/search/rebuild

全量重建索引（换目录/索引损坏时用）→ `data: {"indexed": 42}`。

首次查询时若索引目录不存在会自动重建；查询响应直达打开笔记由前端完成。

## 6. AI 助手（FR-11）

### POST /api/ai/chat

```json
{ "messages": [{"role": "user", "content": "帮我解释这段代码"}],
  "context": "<可选：当前笔记内容>",
  "ai": { "base_url": "https://api.deepseek.com/v1", "api_key": "sk-…", "model": "deepseek-chat" } }
```

`ai` 字段可选：浏览器 ⚙️ 配置存 localStorage、随请求透传，**优先于服务端 env**；
只在本机 backend 转发使用，不落盘、不回显。本地 Ollama 允许 key 留空。
兼容别名：`question` / `prompt`（等价单条 user 消息）。

成功：`data: {"reply": "...", "model": "deepseek-chat"}`
失败：`AI_NOT_CONFIGURED`(400) / `AI_UPSTREAM_ERROR`(502)。

### POST /api/ai/test（功能四）

请求体同 `/api/ai/chat` 的 `ai` 字段（可空 → 测服务端 env 默认配置）：
`{"ai": {"base_url","api_key","model"}}`。后端发一条最短消息（20s 超时）验证三件套。

成功：`data: {"message":"连接成功","model","echo"}`；失败：`AI_NOT_CONFIGURED` / `AI_UPSTREAM_ERROR`。
**不写任何配置**——保存动作始终由前端「保存」按钮完成（localStorage）。

### 聊天记录（功能五）：与笔记绑定

存储：`notebooks/<笔记同名>.ai-chat.json`，结构
`{"note":"示例笔记.md","messages":[{"role","content","time"}]}`。
后端校验：role ∈ {user,assistant,system}、内容非空且截断 50k、条数上限 500，非法条目静默过滤。

| 方法 | 路径 | 说明 | `data` |
|------|------|------|--------|
| GET | `/api/ai/chat/<note>` | 读取（不存在/损坏返回空列表） | `{"note","messages"}` |
| POST | `/api/ai/chat/<note>` | 全量保存 `{"messages":[…]}`（原子写；空列表=删除文件） | `{"note","saved":N}` |
| DELETE | `/api/ai/chat/<note>` | 清空 | `{"note","cleared":true}` |

生命周期联动：**笔记删除 → 记录随之删除；笔记改名 → 记录随之迁移**；
前端在笔记**首次另存/换名**时把暂挂旧名（如 `未命名.md`）下的会话迁移到新名。
`.ai-chat.json` 已被 `.gitignore` 显式排除，永不入库。

## 7. Git 同步（FR-12，阶段三）

| 方法 | 路径 | `data` |
|------|------|--------|
| GET | `/api/git/status` | `{"initialized","branch","changed"}` |
| POST | `/api/git/init` | `{"initialized":true,…}` |
| POST | `/api/git/commit` | `{"committed":true,"sha"}` |
| POST | `/api/git/push` / `pull` | 命令输出摘要 |

失败统一 `GIT_ERROR`（未装 GitPython/未初始化时 `message` 含引导）。

## 8. 静态资源（exe/生产例外）

非 `/api` 路径由 Flask 纯静态托管 `frontend/dist`（Vite 产物）。
未构建时 `GET /` 返回 `NOT_FOUND` 信封 + 构建指引（`message` 含 `npm` 命令）。
