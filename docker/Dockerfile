# =============================================================================
# 代码执行沙箱镜像（NFR-01）
# 后端 EXECUTOR_MODE=docker 时，用该镜像以“一次性容器”运行笔记中的代码块：
#   docker run --rm --memory 256m --cpus 0.5 --network none \
#     --read-only -v <tmpdir>:/sandbox:ro markdown-notebook-sandbox python /sandbox/main.py
# =============================================================================
FROM python:3.11-slim

# 常用科学计算/绘图库（数据科学家用户画像，可按需增删）
RUN pip install --no-cache-dir numpy pandas matplotlib

# 非 root 用户运行，进一步收敛权限
RUN useradd -m -u 1000 sandbox
USER sandbox
WORKDIR /sandbox

# 默认命令：运行挂载进来的脚本（后端会显式传入完整命令，这里仅作兜底）
CMD ["python", "-I", "-B", "/sandbox/main.py"]
