"""Flask API 冒烟测试 v0.3（test_client，无需监听端口）。

用法：cd backend && python _smoke.py
通过标准：最后一行输出 SMOKE OK。
覆盖：统一信封 / 执行与参数 / 渲染解析 / 环境探测 / Whoosh 搜索
（含保存联动、删除清索引、重建）/ 笔记 CRUD / 路径防护 / 静态托管 / AI 降级。
"""
import os
import sys

try:  # Windows GBK 控制台兜底
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".deps"))

from app import app  # noqa: E402

client = app.test_client()
FAIL = []


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
    assert data_of(r)["indexed"] >= 1, r
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

print("SMOKE OK" if not FAIL else f"SMOKE FAILED: {FAIL}")
sys.exit(0 if not FAIL else 1)
