# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 —— markdown-notebook（Windows x64 单文件 exe）。

构建：pyinstaller --noconfirm --clean markdown-notebook.spec
（推荐直接运行 build.bat 或 CI，会先执行 tools/fetch_assets.py 镜像前端资源）

关键决策：
  • onefile：整包一个 exe（首启动解压到 _MEIPASS，稍慢 1~2s，换取分发简单）；
  • console=True：Werkzeug 日志可见、Ctrl+C 干净停止；若打包为无窗口版，
    sys.stdout=None 会让日志写入崩溃，需另行处理，故选择带控制台；
  • datas：frontend/ 整目录（含 vendor/ 离线资产）随包分发——Monaco 等
    PyInstaller 无法自动发现的静态文件必须显式包含；
  • hiddenimports：markdown 扩展按字符串名动态加载、GitPython 是函数内
    懒导入，静态分析会漏，需显式声明；
  • 代码执行用 subprocess 调用**本机**解释器（打包版 sys.executable 是 exe
    自身，executors/python_executor.py 已做探测）；exe 体积因此不含解释器，
    使用说明中已提示用户自装 Python 或用 Docker 模式。
"""
import os

block_cipher = None

ICON = "packaging/icon.ico" if os.path.isfile("packaging/icon.ico") else None

# 随包分发的数据目录：(源, 包内目标)
datas = [
    ("frontend", "frontend"),
]

hiddenimports = [
    # Markdown 扩展按名字动态导入
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    "markdown.extensions.toc",
    "markdown.extensions.codehilite",
    "markdown.extensions.nl2br",
    # 可选依赖（requirements.txt 均有）
    "flask_cors",
    "requests",
    "git",       # GitPython：git_service 内懒导入
    "gitdb",
    "smmap",
    # Pygments 注册表（一般由 contrib hook 处理，保险起见显式列出）
    "pygments.lexers._mapping",
    "pygments.formatters._mapping",
    "pygments.styles._mapping",
]

a = Analysis(
    [os.path.join("backend", "app.py")],
    pathex=["backend"],                     # config/executors/parsers/services 为顶层模块
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # 构建机若全局装了大包，防误入
    excludes=[
        "tkinter", "PyQt5", "PySide2", "numpy", "scipy", "pandas",
        "matplotlib", "IPython", "pytest", "setuptools", "pip",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="markdown-notebook",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                              # CI 无 UPX，保持可复现
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
