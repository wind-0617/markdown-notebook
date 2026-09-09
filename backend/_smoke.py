"""Flask API 冒烟测试（test_client，无需监听端口）。

用法：cd backend && python _smoke.py
通过标准：最后一行输出 SMOKE OK。可删除本文件。
"""
import os
import sys

try:  # Windows GBK 控制台兜底：允许打印 emoji/UTF-8 文案
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".deps"))

from app import app  # noqa: E402

client = app.test_client()

# 1) 健康检查
h = client.get("/api/health").get_json()
assert h["ok"] and "python" in h["languages"], h
print("health ok:", h["executor_mode"], h["languages"])

# 2) 代码执行（FR-03）
r = client.post("/api/execute", json={"language": "python", "code": "print('hello', 40+2)"}).get_json()
assert r["exit_code"] == 0 and "hello 42" in r["stdout"], r
print("execute ok:", r["stdout"].strip(), f"{r['duration_ms']}ms")

# 3) 不支持语言返回 400
bad = client.post("/api/execute", json={"language": "ruby", "code": "puts 1"})
assert bad.status_code == 400 and "languages" in bad.get_json(), bad
print("bad-language ok:", bad.status_code)

# 4) 交互参数经后端展开执行（FR-07/08）
code = "# @param n 数量 slider min=1 max=10 default=3\nprint(n * 7)"
rp = client.post("/api/execute", json={"language": "python", "code": code, "params": {"n": 6}}).get_json()
assert rp["exit_code"] == 0 and rp["stdout"].strip() == "42", rp
print("param-execute ok:", rp["stdout"].strip())

# 5) 服务端渲染（FR-02 备用链路）
rd = client.post("/api/render", json={"markdown": "# 标题\n\n```python\nprint(1)\n```"}).get_json()
assert "<h1" in rd["html"], rd
print("render ok:", rd["html"][:40].replace("\n", " "), "…")

# 6) 解析接口（/api/parse）
pa = client.post("/api/parse", json={"markdown": "```python\n# @param x 值 slider min=0 max=9 default=5\nprint(x)\n```"}).get_json()
b0 = pa["blocks"][0]
assert b0["runnable"] and b0["params"][0]["name"] == "x", pa
print("parse ok:", b0["language"], b0["params"][0])

# 7) 笔记 CRUD 闭环（FR-05）
resp = client.post("/api/notes", json={"name": "_smoke.md"}).get_json()
assert resp.get("created"), resp
s = client.put("/api/notes/_smoke.md", json={"content": "# smoke\n"}).get_json()
assert s.get("saved"), s
g = client.get("/api/notes/_smoke.md").get_json()
assert g["content"] == "# smoke\n", g
names = [n["name"] for n in client.get("/api/notes").get_json()["notes"]]
assert "_smoke.md" in names, names
d = client.delete("/api/notes/_smoke.md").get_json()
assert d.get("deleted"), d
print("notes crud ok")

# 8) 路径穿越防护（NFR-01）：路由层 404 或校验层 400 都算拦截成功
evil = client.get("/api/notes/..%2F..%2Fapp.py")
assert evil.status_code in (400, 404), evil.status_code
evil2 = client.put("/api/notes/evil.txt", json={"content": "x"})
assert evil2.status_code == 400, evil2  # 非 .md 文件名校验
print("path-guard ok")

# 9) 前端静态资源可达
idx = client.get("/")
assert idx.status_code == 200 and b"Monaco" in idx.data, idx.status_code
js = client.get("/js/app.js")
assert js.status_code == 200, js.status_code
print("static ok")

# 10) AI 未配置时优雅降级（FR-11）
ai = client.post("/api/ai/chat", json={"prompt": "hi"})
assert ai.status_code in (200, 503) and "ok" in ai.get_json(), ai
print("ai-degrade ok:", ai.get_json().get("error") or ai.get_json().get("reply")[:30])

print("SMOKE OK")
