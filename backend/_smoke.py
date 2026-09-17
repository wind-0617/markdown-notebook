"""Flask API 冒烟测试 v0.3（test_client，无需监听端口）。

用法：venv/Scripts/python.exe backend/_smoke.py
通过标准：最后一行输出 SMOKE OK。
覆盖：统一信封 / 执行与参数 / 渲染解析 / 环境探测 / Whoosh 搜索
（含保存联动、删除清索引、重建）/ 笔记 CRUD / 路径防护 / 静态托管 / AI 降级
/ 重命名 / 导出下载 / AI 测试连接 / AI 聊天记录持久化。

隔离：在 import app 之前把 NOTEBOOKS_DIR / SEARCH_INDEX_DIR 指向一次性
临时目录——冒烟测试绝不读写用户真实笔记，且每次都是干净索引。
"""
import os
import shutil
import sys
import tempfile

try:  # Windows GBK 控制台兜底
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".deps"))

_TMP = tempfile.mkdtemp(prefix="nb-smoke-")
os.environ["NOTEBOOKS_DIR"] = os.path.join(_TMP, "notebooks")
os.environ["SEARCH_INDEX_DIR"] = os.path.join(_TMP, "index")
os.makedirs(os.environ["NOTEBOOKS_DIR"], exist_ok=True)

from app import app  # noqa: E402

client = app.test_client()
FAIL = []


def _cleanup_tmp() -> None:
    try:
        shutil.rmtree(_TMP, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass


def data_of(resp):
    j = resp.get_json()
    assert j["success"] is True and j["error"] is None, j
    return j["data"]


def check(label, fn):
    try:
        fn()
        print(f"ok   {label}")
    except AssertionError as exc:
        print(f"FAIL {label}: {exc}")
        FAIL.append(label)


# 1) 健康检查（信封 + 语言状态）
def t_health():
    h = data_of(client.get("/api/health"))
    langs = {l["language"]: l for l in h["languages"]}
    assert h["frozen"] is False and "python" in langs and langs["python"]["registered"], h
check("health", t_health)

# 2) 代码执行
def t_exec():
    r = data_of(client.post("/api/execute", json={"language": "python", "code": "print('hello', 40+2)"}))
    assert r["exit_code"] == 0 and "hello 42" in r["stdout"], r
check("execute", t_exec)

# 3) 不支持语言 → 信封失败 + 错误码
def t_badlang():
    resp = client.post("/api/execute", json={"language": "ruby", "code": "x"})
    j = resp.get_json()
    assert resp.status_code == 400 and j["error"]["code"] == "LANGUAGE_UNSUPPORTED", j
    assert "languages" in j["error"]["details"], j
check("bad-language", t_badlang)

# 4) 交互参数
def t_param():
    code = "# @param n 数量 slider min=1 max=10 default=3\nprint(n * 7)"
    r = data_of(client.post("/api/execute", json={"language": "python", "code": code, "params": {"n": 6}}))
    assert r["exit_code"] == 0 and r["stdout"].strip() == "42", r
check("param-execute", t_param)

# 5) 渲染 / 解析
def t_render():
    d = data_of(client.post("/api/render", json={"markdown": "# 标题\n\n```python\nprint(1)\n```"}))
    assert "<h1" in d["html"], d
    p = data_of(client.post("/api/parse", json={"markdown": "```python\n# @param x 值 slider min=0 max=9 default=5\nprint(x)\n```"}))
    b0 = p["blocks"][0]
    assert b0["runnable"] and b0["params"][0]["name"] == "x", p
check("render+parse", t_render)

# 6) 环境探测
def t_env():
    d = data_of(client.get("/api/environment/check?lang=python"))
    assert d["available"] and d["version"], d
    d2 = data_of(client.get("/api/environment/check?lang=java"))
    assert d2["language"] == "java" and "available" in d2, d2
    assert client.get("/api/environment/check").status_code == 400
check("environment", t_env)

# 7) 搜索：保存联动 / 中文与代码关键词 / 高亮 / 删除清索引 / 重建
UNIQ = "鹈鹕"  # 罕见词做定位用
NOTE = "_smoke_search.md"


def t_search():
    r = client.post("/api/search/rebuild")
    assert data_of(r)["indexed"] >= 0, r          # 隔离空目录可为 0，只验接口可用
    content = f"# 检索试验\n\n{UNIQ}是一种大型鸟类，可执行代码在下面。\n\n```python\nprint('searchable-py')\n```\n"
    data_of(client.put(f"/api/notes/{NOTE}", json={"content": content}))  # 保存即建索引
    hits = data_of(client.get(f"/api/search?q={UNIQ}"))["results"]
    assert hits and hits[0]["name"] == NOTE, hits
    assert "<u>" in hits[0]["snippet"], hits[0]           # 关键词高亮
    assert hits[0]["title"] == "检索试验" and hits[0]["modified"] > 0, hits[0]
    hits2 = data_of(client.get("/api/search?q=searchable-py"))["results"]
    assert any(h["name"] == NOTE for h in hits2), hits2   # 代码内容可检索
    # 删除后不应再命中
    data_of(client.delete(f"/api/notes/{NOTE}"))
    hits3 = data_of(client.get(f"/api/search?q={UNIQ}"))["results"]
    assert all(h["name"] != NOTE for h in hits3), hits3
    assert client.get("/api/search?q=").status_code == 400
check("search(whoosh)", t_search)

# 8) 笔记 CRUD 闭环
def t_notes():
    d = data_of(client.post("/api/notes", json={"name": "_smoke.md"}))
    assert d.get("created"), d
    s = data_of(client.put("/api/notes/_smoke.md", json={"content": "# smoke\n"}))
    assert s.get("saved"), s
    g = data_of(client.get("/api/notes/_smoke.md"))
    assert g["content"] == "# smoke\n", g
    names = [n["name"] for n in data_of(client.get("/api/notes"))["notes"]]
    assert "_smoke.md" in names, names
    assert data_of(client.delete("/api/notes/_smoke.md")).get("deleted")
check("notes-crud", t_notes)

# 9) 路径穿越防护
def t_guard():
    evil = client.get("/api/notes/..%2F..%2Fapp.py")
    assert evil.status_code in (400, 404), evil.status_code
    evil2 = client.put("/api/notes/evil.txt", json={"content": "x"})
    j = evil2.get_json()
    assert evil2.status_code == 400 and j["error"]["code"] == "NOTE_NAME_INVALID", j
check("path-guard", t_guard)

# 10) 静态托管：dist 已构建则 200+SPA 骨架；未构建则信封 404 带指引（两者皆合法）
def t_static():
    idx = client.get("/")
    if idx.status_code == 200:
        assert b'id="editor"' in idx.data and b"/assets/" in idx.data, idx.data[:200]
        asset = client.get("/api/not-an-asset-but-api")
        assert asset.status_code == 404 and asset.get_json()["error"]["code"] == "NOT_FOUND"
    else:
        j = idx.get_json()
        assert j["error"]["message"] and "npm" in j["error"]["message"], j
check("static-hosting", t_static)

# 11) AI 未配置降级（本机无 env key 场景）
def t_ai():
    resp = client.post("/api/ai/chat", json={"question": "hi"})
    j = resp.get_json()
    if app.config["AI_API_KEY"] or app.config["AI_MODEL"] != "gpt-4o-mini":
        return  # 配置了真实上游则跳过断言
    assert j["success"] is False and j["error"]["code"] == "AI_NOT_CONFIGURED", j
check("ai-degrade", t_ai)

# ============ v0.3.1 新增：重命名 / 导出 / 测试连接 / 聊天记录 ============
from urllib.parse import quote  # noqa: E402

# 12) 重命名（功能一）
def t_rename():
    data_of(client.post("/api/notes", json={"name": "_ren_a.md", "content": "# 甲\n"}))
    d = data_of(client.post("/api/notes/rename", json={"old_path": "_ren_a.md", "new_name": "重命名后"}))
    assert d["name"] == "重命名后.md" and d.get("renamed"), d
    assert client.get("/api/notes/_ren_a.md").status_code == 404      # 旧名已消失
    assert data_of(client.get("/api/notes/重命名后.md"))["content"] == "# 甲\n"
    hits = data_of(client.get("/api/search?q=" + quote("重命名后")))["results"]
    assert any(h["name"] == "重命名后.md" for h in hits), hits         # 索引跟随改名
    data_of(client.post("/api/notes", json={"name": "_ren_c.md"}))
    j = client.post("/api/notes/rename", json={"old_path": "重命名后.md", "new_name": "_ren_c.md"}).get_json()
    assert j["error"]["code"] == "NOTE_EXISTS", j                     # 重名冲突
    j2 = client.post("/api/notes/rename", json={"old_path": "_ren_c.md", "new_name": "a/b:c*d?e"}).get_json()
    assert j2["error"]["code"] == "NOTE_NAME_INVALID", j2             # 非法字符 /\:*?"<>|
    j2b = client.post("/api/notes/rename", json={"old_path": "_ren_c.md", "new_name": "x/y\\z"}).get_json()
    assert j2b["error"]["code"] == "NOTE_NAME_INVALID", j2b           # 显式拒绝，不静默净化成 z.md
    j3 = client.post("/api/notes/rename", json={"old_path": "../app.py", "new_name": "x.md"}).get_json()
    assert j3["error"]["code"] in ("NOTE_NAME_INVALID", "NOT_FOUND"), j3  # 路径穿越被拦截
    for n in ("重命名后.md", "_ren_c.md"):
        data_of(client.delete(f"/api/notes/{n}"))
check("rename", t_rename)

# 13) 导出下载（功能三）
def t_export():
    content = "# 导出\n中文内容 ok\n"
    data_of(client.post("/api/notes", json={"name": "导出测试.md", "content": content}))
    r = client.get("/api/notes/导出测试.md/export")
    try:
        assert r.status_code == 200, r.status_code
        cd = r.headers.get("Content-Disposition", "")
        assert "attachment" in cd and "filename" in cd.lower(), cd        # 强制下载头
        assert "utf-8''" in cd.lower() or "%E" in cd, cd                  # 中文名 RFC 5987 编码
        # 导出返回原始字节：Windows 落盘为 CRLF，断言按原始文本语义归一换行
        assert r.get_data(as_text=True).replace("\r\n", "\n") == content, repr(r.get_data(as_text=True))[:120]
    finally:
        r.close()   # send_from_directory 的文件句柄挂在响应上：真服务器由请求结束关闭，测试须显式关
    assert client.get("/api/notes/不存在.md/export").status_code == 404
    data_of(client.delete("/api/notes/导出测试.md"))
check("export", t_export)

# 14) 测试连接（功能四）
def t_aitest():
    if app.config["AI_API_KEY"]:
        return                                                        # 有真实 env 配置则跳过
    j = client.post("/api/ai/test", json={}).get_json()
    assert j["success"] is False and j["error"]["code"] == "AI_NOT_CONFIGURED", j
    j2 = client.post("/api/ai/test", json={
        "ai": {"base_url": "http://127.0.0.1:9/v1", "model": "x", "api_key": "k"}}).get_json()
    assert j2["success"] is False and j2["error"]["code"] == "AI_UPSTREAM_ERROR", j2
check("ai-test", t_aitest)

# 15) 聊天记录（功能五）：保存/读取/过滤/随删/随改名/清空
def t_chat():
    data_of(client.post("/api/notes", json={"name": "_chat_host.md", "content": "# c\n"}))
    msgs = [{"role": "user", "content": "你好", "time": "2026-09-18 10:00"},
            {"role": "assistant", "content": "你好，有什么可以帮你？"}]
    d = data_of(client.post("/api/ai/chat/_chat_host.md", json={"messages": msgs}))
    assert d["saved"] == 2, d
    g = data_of(client.get("/api/ai/chat/_chat_host.md"))
    assert g["messages"][0]["content"] == "你好" and g["messages"][0]["time"], g
    d2 = data_of(client.post("/api/ai/chat/_chat_host.md", json={
        "messages": msgs + [{"role": "hacker", "content": "x"}, {"role": "user", "content": ""},
                             {"role": "user", "content": 3}]}))
    assert d2["saved"] == 3, d2                                       # role/空文过滤，合法保留
    data_of(client.delete("/api/notes/_chat_host.md"))                # 删除笔记
    assert data_of(client.get("/api/ai/chat/_chat_host.md"))["messages"] == []   # 记录一并清除
    data_of(client.post("/api/notes", json={"name": "_chat_old.md"}))
    data_of(client.post("/api/ai/chat/_chat_old.md", json={"messages": [{"role": "user", "content": "跟着搬家"}]}))
    data_of(client.post("/api/notes/rename", json={"old_path": "_chat_old.md", "new_name": "_chat_new.md"}))
    got = data_of(client.get("/api/ai/chat/_chat_new.md"))["messages"]
    assert got and got[0]["content"] == "跟着搬家", got                # 改名记录跟随
    data_of(client.delete("/api/ai/chat/_chat_new.md"))               # 显式清空接口
    assert data_of(client.get("/api/ai/chat/_chat_new.md"))["messages"] == []
    assert client.post("/api/ai/chat/x.md", json={"messages": "不是列表"}).status_code == 400
    jv = client.post("/api/ai/chat/非法名!.md", json={"messages": []}).get_json()
    assert jv["error"]["code"] == "NOTE_NAME_INVALID", jv
    client.delete("/api/notes/_chat_new.md")
check("ai-chat-store", t_chat)

_cleanup_tmp()
print("SMOKE OK" if not FAIL else f"SMOKE FAILED: {FAIL}")
sys.exit(0 if not FAIL else 1)
