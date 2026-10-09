@echo off
title EDITH Landing Page Server
cd /d "%~dp0"
echo Starting EDITH Landing Page Server on http://localhost:3000/ ...
node server.js
pause
