# API 文档

> Base URL：`http://127.0.0.1:5000` ｜ 全部为 JSON；错误统一返回 `{"error": "..."}`。

## 1. 基础

### GET /api/health
健康检查与能力探测。

```json
{
  "ok": true,
  "version": "0.1.0",
  "executor_mode": "local",
  "languages": ["javascript", "python", "shell"],
  "ai_enabled": false
}
```

## 2. 渲染与解析

### POST /api/render
请求：`{"markdown": "# hi"}` → 响应：`{"html": "<h1>hi</h1>"}`

### POST /api/parse
提取代码块与交互参数（前端渲染控件时用）。

请求：`{"markdown": "<全文>"}` → 响应：

```json
{
  "blocks": [{
    "index": 0,
    "language": "python",
    "raw_language": "python",
    "code": "# @param n 数量 slider min=1 max=10 default=3\nprint(n)",
    "start_line": 4,
    "runnable": true,
    "params": [
      {"name": "n", "label": "数量", "kind": "slider",
       "min": 1, "max": 10, "step": null, "default": 3.0, "options": []}
    ]
  }]
}
```

## 3. 代码执行（FR-03 / FR-08）

### POST /api/execute

| 字段 | 类型 | 说明 |
|------|------|------|
| `language` | string | `python` \| `javascript` \| `shell`（默认 python） |
| `code` | string | 代码正文（交互参数已展开或另行传 `params`） |
| `params` | object，可选 | `{name: value}`；服务端自动删 @param 行并注入赋值 |
| `timeout` | int，可选 | 1~120 秒，默认取 `EXEC_TIMEOUT`（30） |

请求示例：

```json
{"language": "python", "code": "print(6*7)"}
```

响应（成功/失败/超时都返回 200，用字段区分）：

```json
{
  "stdout": "42\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 213,
  "timed_out": false,
  "language": "python",
  "extra": {}
}
```

错误码：`400` 不支持的语言（响应含 `languages` 候选列表）。

## 4. 笔记管理（FR-05）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/notes` | 列表 → `{"notes":[{name,size,modified}]}` |
| GET | `/api/notes/<name>` | 读取 → `{"name","content"}` |
| POST | `/api/notes` | 新建 `{"name","content"?}` |
| PUT | `/api/notes/<name>` | 保存 `{"content"}` → `{"saved":true}` |
| DELETE | `/api/notes/<name>` | 删除 |

约束：文件名仅允许中文/字母/数字/空格/`.()-_`，必须 `.md` 结尾；违规返回 400。

## 5. AI 助手（FR-11）

### POST /api/ai/chat

```json
{
  "messages": [{"role": "user", "content": "帮我解释这段代码"}],
  "context": "<可选：当前笔记内容>",
  "ai": {
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "sk-…",
    "model": "deepseek-chat"
  }
}
```

`ai` 字段可选：浏览器端在 ⚙️ 设置弹窗配置、存 localStorage，随后端请求透传，
**优先于服务端环境变量默认值**；仅本机 backend 转发使用，不写盘、不回显。
本地 Ollama（`http://localhost:11434/v1`）允许 api_key 留空。

成功（200）：`{"ok": true, "reply": "...", "model": "deepseek-chat"}`
失败（503）：`{"ok": false, "error": "未配置 API Key…（含 ⚙️ 操作指引）"}`

## 6. Git 同步（FR-12，阶段三）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/git/status` | `{"initialized","branch","changed"}` |
| POST | `/api/git/init` | 初始化 notebooks 仓库 |
| POST | `/api/git/commit` | `{"message"}` → `{"committed","sha"}` |
| POST | `/api/git/push` / `pull` | `{"remote"?, 默认 origin}` |

未初始化/未安装 GitPython 时返回 400 + 引导性 `error` 信息。

## 7. 错误码约定

| HTTP | 场景 |
|------|------|
| 400 | 参数不合法（语言不支持、文件名违规、Git 未初始化） |
| 404 | API 路径不存在 |
| 500 | 服务端内部错误（返回 JSON `error`） |
| 503 | AI 服务不可用/未配置 |
