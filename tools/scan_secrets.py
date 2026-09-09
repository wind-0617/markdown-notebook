# -*- coding: utf-8 -*-
"""扫描 git 暂存区文件中的密钥/凭据特征。用法：python tools/scan_secrets.py"""
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PATTERNS = [
    ("OpenAI 风格 Key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("GitHub Token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("AWS Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("私钥块", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY")),
    ("Slack", re.compile(r"\bxox[bpars]-[A-Za-z0-9\-]{10,}")),
    ("key=value 赋值", re.compile(
        r"""(?i)(api[_-]?key|apikey|secret|access[_-]?token|auth[_-]?token|password|passwd|pwd)\s*[=:]\s*['"]([^'"\s]{8,})['"]""")),
    ("Bearer 头", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}")),
    ("URL 内嵌凭据", re.compile(r"https?://[^/\s:@]+:[^/\s@]+@")),
]
ALLOW_EMPTY = re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*['\"]{2}|['\"]\s*(getenv|environ|os\.environ)")

files = subprocess.run(
    ["git", "diff", "--cached", "--name-only", "-z"], capture_output=True
).stdout.decode("utf-8").split("\0")
files = [f for f in files if f]

hits, binary_skipped = [], 0
for f in files:
    try:
        with open(f, "rb") as fh:
            data = fh.read()
    except OSError:
        continue
    if b"\x00" in data[:4096]:
        binary_skipped += 1
        continue
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        for name, pat in PATTERNS:
            m = pat.search(line)
            if not m:
                continue
            # 放行：空串默认值 / 纯环境变量读取 / 明显占位符
            low = line.lower()
            if "your_" in low or "your-" in low or "xxx" in low or "占位" in line or "example" in low:
                continue
            hits.append((f, i, name, line.strip()[:160]))

print(f"扫描文件：{len(files)} 个（跳过二进制 {binary_skipped} 个）")
if hits:
    print(f"\n⚠️ 发现 {len(hits)} 处疑似敏感内容：")
    for f, i, name, line in hits:
        print(f"  [{name}] {f}:{i}\n      {line}")
    sys.exit(1)
print("✅ 未发现密钥/凭据特征")
