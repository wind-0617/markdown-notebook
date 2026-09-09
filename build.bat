@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Markdown Notebook  Windows 打包脚本
echo ============================================
rem 步骤：选 Python → 装构建依赖 → 镜像前端资产 → PyInstaller → 组装 zip

set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"

"%PY%" -V >nul 2>nul
if errorlevel 1 (
  echo [X] 未找到 Python。请先运行一次 run.cmd 自动建 venv，或安装 Python3 并入 PATH。
  exit /b 1
)

echo [1/4] 检查构建依赖 ...
"%PY%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
  echo     安装 PyInstaller 与运行依赖 ...
  "%PY%" -m pip install -q -r backend\requirements.txt "pyinstaller>=6,<7"
  if errorlevel 1 ( echo [X] 依赖安装失败 & exit /b 1 )
)

echo [2/4] 镜像前端静态资产（Monaco/marked/hljs → frontend\vendor）...
"%PY%" tools\fetch_assets.py
if errorlevel 1 (
  echo [X] 资产下载失败：检查网络，或设置镜像 NPM_REGISTRY_URL / CDN_BASE_URL 后重试。
  exit /b 1
)

echo [3/4] PyInstaller 构建 ...
"%PY%" -m PyInstaller --noconfirm --clean markdown-notebook.spec
if errorlevel 1 ( echo [X] 构建失败，见上方日志 & exit /b 1 )

echo [4/4] 组装发布 zip ...
"%PY%" tools\package_dist.py
if errorlevel 1 ( echo [X] 打包失败 & exit /b 1 )

echo.
echo 🎉 完成！产物在 dist\markdown-notebook-windows-x64.zip
pause
