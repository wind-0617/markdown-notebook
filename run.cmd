@echo off
rem run.cmd —— Windows 双击启动包装器（绕过执行策略限制）
rem 等效于：powershell -ExecutionPolicy Bypass -File run.ps1
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
