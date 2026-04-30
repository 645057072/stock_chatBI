@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .env (
  echo 未找到 .env，从 .env.example 复制后请填写 DASHSCOPE_API_KEY
  copy /Y .env.example .env
)
docker compose up -d --build
echo.
echo 默认 HTTP  端口见 .env 中 CHATBI_HTTP_PORT（未改则为 18080）
echo 默认 HTTPS 端口见 .env 中 CHATBI_HTTPS_PORT（未改则为 18443，镜像内为自签名证书）
pause
