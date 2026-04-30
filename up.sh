#!/usr/bin/env bash
# ChatBI：Linux 下一键启动前检测宿主机端口是否已被占用，避免与 ECS 上其它系统冲突。
# 用法：chmod +x up.sh && ./up.sh
# 跳过检测（不推荐）：SKIP_PORT_CHECK=1 ./up.sh

set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "未找到 .env，从 .env.example 复制后请至少填写 DASHSCOPE_API_KEY 等变量。"
  cp -n .env.example .env 2>/dev/null || true
fi

# 读取端口（与 docker-compose.yml 中变量一致）
set -a
# shellcheck disable=SC1091
[[ -f .env ]] && source ./.env
set +a

HTTP_PORT="${CHATBI_HTTP_PORT:-18080}"
HTTPS_PORT="${CHATBI_HTTPS_PORT:-18443}"

# 若本机端口已被监听，返回 0（占用）
port_is_listening() {
  local port="$1"
  if ! command -v ss >/dev/null 2>&1; then
    echo "警告：未找到 ss 命令，无法检测端口 ${port}，请自行确认未被占用。" >&2
    return 1
  fi
  # 取本地地址列，匹配末尾 :端口，避免 18080 误匹配 180800
  ss -tuln -H 2>/dev/null | awk '{print $5}' | grep -qE ":${port}$"
}

if [[ "${SKIP_PORT_CHECK:-0}" != "1" ]]; then
  occupied=0
  if port_is_listening "$HTTP_PORT"; then
    echo "错误：HTTP 映射端口 ${HTTP_PORT} 已被占用（CHATBI_HTTP_PORT）。请修改 .env 或释放端口，避免影响其它系统。"
    ss -tuln -H 2>/dev/null | awk -v p=":${HTTP_PORT}$" '$5 ~ p {print}' || true
    occupied=1
  fi
  if port_is_listening "$HTTPS_PORT"; then
    echo "错误：HTTPS 映射端口 ${HTTPS_PORT} 已被占用（CHATBI_HTTPS_PORT）。请修改 .env 或释放端口。"
    ss -tuln -H 2>/dev/null | awk -v p=":${HTTPS_PORT}$" '$5 ~ p {print}' || true
    occupied=1
  fi
  if [[ "$occupied" -ne 0 ]]; then
    echo "已中止启动。若确认无冲突可执行：SKIP_PORT_CHECK=1 ./up.sh"
    exit 1
  fi
fi

if [[ -z "${COMPOSE_PROJECT_NAME:-}" ]]; then
  echo "提示：建议在 .env 中设置 COMPOSE_PROJECT_NAME（例如 chatbi_case_prod），以便与其它 Docker 项目网络/卷隔离。"
fi

docker compose up -d --build

echo ""
echo "已启动。HTTP  访问宿主机端口：${HTTP_PORT}"
echo "         HTTPS 访问宿主机端口：${HTTPS_PORT}（镜像内自签名证书时浏览器需信任）"
