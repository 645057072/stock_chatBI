@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .env (
  echo 未找到 .env，从 .env.example 复制后请填写 DASHSCOPE_API_KEY
  copy /Y .env.example .env
)
if "%COMPOSE_PROJECT_NAME%"=="" (
  echo 提示：建议设置 COMPOSE_PROJECT_NAME 以隔离网络/卷，例如 chatbi_case_prod
)
docker compose up -d --build
echo.
echo === nginx（页面与 /api 反代；须为 Up，否则浏览器「连接被拒绝」）===
docker compose ps -a nginx
echo.
echo 默认 HTTP  端口见 .env 中 CHATBI_HTTP_PORT（未改则为 18080）
echo 默认 HTTPS 端口见 .env 中 CHATBI_HTTPS_PORT（未改则为 18443，镜像内为自签名证书）
echo ECS/Linux：MySQL、Redis 默认仅 Docker 网络内访问（容器内 3309/6381）；本地调试可在 compose 中临时加 ports 映射。
pause
