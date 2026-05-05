#!/usr/bin/env bash
# ChatBI：Linux 下一键启动（仅检测 Nginx 对外端口，避免与 ECS 其它 Web 冲突）
# MySQL/Redis 默认不映射宿主机端口，无需检测 3309/6381
# 用法：chmod +x up.sh && ./up.sh
# 跳过检测：SKIP_PORT_CHECK=1 ./up.sh

set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "未找到 .env，从 .env.example 复制后请至少填写 MYSQL_ROOT_PASSWORD、DASHSCOPE_API_KEY 等。"
  cp -n .env.example .env 2>/dev/null || true
fi

set -a
# shellcheck disable=SC1091
[[ -f .env ]] && source ./.env
set +a

HTTP_PORT="${CHATBI_HTTP_PORT:-18080}"
HTTPS_PORT="${CHATBI_HTTPS_PORT:-18443}"

port_is_listening() {
  local port="$1"
  if ! command -v ss >/dev/null 2>&1; then
    echo "警告：未找到 ss 命令，无法检测端口 ${port}。" >&2
    return 1
  fi
  ss -tuln -H 2>/dev/null | awk '{print $5}' | grep -qE ":${port}$"
}

if [[ "${SKIP_PORT_CHECK:-0}" != "1" ]]; then
  occupied=0
  if [[ "$HTTP_PORT" == "80" || "$HTTP_PORT" == "443" ]]; then
    echo "警告：CHATBI_HTTP_PORT=${HTTP_PORT} 可能与其它系统 Web 入口冲突，建议使用非常用端口（如 18080、28080）。" >&2
  fi
  if port_is_listening "$HTTP_PORT"; then
    echo "错误：HTTP 映射端口 ${HTTP_PORT}（CHATBI_HTTP_PORT）已被占用。请在 .env 中改为未占用端口（例如 28080）后重试。"
    ss -tuln -H 2>/dev/null | awk -v p=":${HTTP_PORT}$" '$5 ~ p {print}' || true
    occupied=1
  fi
  if port_is_listening "$HTTPS_PORT"; then
    echo "错误：HTTPS 映射端口 ${HTTPS_PORT}（CHATBI_HTTPS_PORT）已被占用。请在 .env 中修改。"
    ss -tuln -H 2>/dev/null | awk -v p=":${HTTPS_PORT}$" '$5 ~ p {print}' || true
    occupied=1
  fi
  if [[ "$occupied" -ne 0 ]]; then
    echo "已中止启动。若确认无冲突：SKIP_PORT_CHECK=1 ./up.sh"
    exit 1
  fi
fi

if [[ -z "${COMPOSE_PROJECT_NAME:-}" ]]; then
  echo "提示：建议在 .env 中设置 COMPOSE_PROJECT_NAME，以便与其它 Docker 项目隔离。"
fi

docker compose up -d --build

echo ""
echo "=== nginx（页面与 /api 反代；若未运行则浏览器报「连接被拒绝」）==="
docker compose ps -a nginx 2>/dev/null || true

echo ""
echo "已启动。HTTP  http://<ECS IP>:${HTTP_PORT}"
echo "       HTTPS https://<ECS IP>:${HTTPS_PORT}"
echo "MySQL/Redis 仅在 Docker 网络内（服务名 mysql、redis），未绑定宿主机端口。"
