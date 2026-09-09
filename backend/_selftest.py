"""框架自检（无第三方依赖）：执行器真实跑码 + 交互参数解析。

用法：python backend/_selftest.py
通过后会打印 OK，可删除本文件。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from executors import get_executor, supported_languages
from parsers.param_parser import build_executable_code, parse_param_line

# 1) 执行器注册
langs = supported_languages()
assert "python" in langs and "javascript" in langs and "shell" in langs, langs
print("languages:", langs)

# 2) Python 真实执行
res = get_executor("python").run("print(6*7)\nimport sys; print(sys.version_info[0])", timeout=20)
assert res.exit_code == 0 and "42" in res.stdout, res
print("python exec ok:", res.stdout.strip().replace("\n", " | "), f"({res.duration_ms}ms)")

# 3) 超时保护
slow = get_executor("python").run("import time; time.sleep(30)", timeout=2)
assert slow.timed_out and slow.exit_code == -1, slow
print("timeout guard ok:", slow.stderr.strip())

# 4) 交互参数解析与注入
line = "# @param n 样本量 slider min=1 max=100 step=1 default=10"
spec = parse_param_line(line)
assert spec and spec.name == "n" and spec.kind == "slider" and spec.default == 10.0, spec
code = line + "\nprint(n * 2)"
exe = build_executable_code("python", code, {"n": 21})
res2 = get_executor("python").run(exe, timeout=20)
assert res2.stdout.strip() == "42", res2
print("param pipeline ok ->", res2.stdout.strip())

print("SELFTEST OK")
