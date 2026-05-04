#!/usr/bin/env bash
# ChatBI：阿里云 ECS 首次部署（生成 .env、构建并启动、打印初始化说明）
# 用法：chmod +x ecs-first-up.sh && ./ecs-first-up.sh

set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "首次部署：未找到 .env，已从 .env.example 复制，请编辑 MYSQL_ROOT_PASSWORD、DASHSCOPE_API_KEY 及对外端口等。"
  cp -n .env.example .env
fi

chmod +x up.sh 2>/dev/null || true
./up.sh

echo ""
echo "=== 容器状态 ==="
docker compose ps

echo ""
echo "初始化说明："
echo "  - MySQL：首次创建数据卷时会自动执行 schema.sql、deploy/init-app.sql。"
echo "  - 中间件：MySQL/Redis 默认仅容器互通，不占宿主机 13306/16379，避免与其它应用冲突。"
echo "  - 连接：可在 .env 中修改 CHATBI_MYSQL_*、REDIS_URL（连接阿里云 RDS/Redis 时需自行删掉 compose 内 mysql/redis 服务或改用外部编排）。"
echo "  - 若 MySQL 曾初始化失败，数据卷可能损坏，需清空后重来：docker compose down -v && ./ecs-first-up.sh"
