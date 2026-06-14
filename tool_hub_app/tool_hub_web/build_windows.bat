@echo off
setlocal

cd /d %~dp0
py -m PyInstaller --noconfirm tool_hub.spec
