# API 文档（v0.3）

> Base URL：`http://127.0.0.1:5000`（后端只提供 JSON API；页面由 Vite 构建产物静态托管，
> 开发态走 Vite 代理 `5173 → 5000`）。
>
> **v0.3 破坏性变更**：全部响应改为统一信封，旧版裸 JSON 不再兼容。

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
| `NOTE_NAME_INVALID` | 400 | 文件名不符合白名单（中文/字母/数字/空格/`.()-_`，须 `.md` 结尾） |
| `NOTE_EXISTS` | 400 | 新建时同名笔记已存在 |
| `LANGUAGE_UNSUPPORTED` | 400 | 未注册执行器（`details.languages` 给候选） |
| `ENVIRONMENT_UNAVAILABLE` | 424 | 本机缺解释器（`details.environment.hint` 给安装引导） |
| `AI_NOT_CONFIGURED` | 400 | AI 未配置（前端据此弹设置窗） |
| `AI_UPSTREAM_ERROR` | 502 | AI 上游报错 |
| `GIT_ERROR` | 400 | Git 操作失败/未初始化 |
| `SEARCH_ERROR` | 500 | 索引损坏且重建失败等 |
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

响应中的 `name` 为**服务端清洗后的真实文件名**。
**新建/保存/删除会同步维护搜索索引**（索引故障不影响笔记操作本身）。

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
