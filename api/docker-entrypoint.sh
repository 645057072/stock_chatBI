#!/bin/sh
# 启动 API 前等待 MySQL / Redis 可解析且端口可达，避免 register 时出现 Name or service not known / 连接拒绝。
set -e

MYSQL_H="${CHATBI_MYSQL_HOST:-${MYSQL_HOST:-mysql}}"
MYSQL_P="${CHATBI_MYSQL_PORT:-${MYSQL_PORT:-3309}}"

# 从 REDIS_URL 解析主机与端口（支持 redis://、rediss://、含密码 URL）；未写端口时默认 6381（与本仓库 compose 一致）
REDIS_HP=$(python -c "import os, urllib.parse as u; p=u.urlparse(os.environ.get('REDIS_URL','redis://redis:6381/0')); h=p.hostname or 'redis'; po=p.port; port=(po if po is not None else 6381); print(h, port)") || true
[ -z "$REDIS_HP" ] && REDIS_HP="redis 6381"
REDIS_H=$(printf '%s' "$REDIS_HP" | awk '{print $1}')
REDIS_P=$(printf '%s' "$REDIS_HP" | awk '{print $2}')
REDIS_H="${REDIS_H:-redis}"
REDIS_P="${REDIS_P:-6381}"

wait_tcp() {
  _label="$1"
  _host="$2"
  _port="$3"
  _max="$4"
  _i=0
  while [ "$_i" -lt "$_max" ]; do
    if python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('${_host}', int('${_port}'))); s.close()" 2>/dev/null; then
      echo "[entrypoint] ${_label} ${_host}:${_port} 已就绪"
      return 0
    fi
    _i=$((_i + 1))
    echo "[entrypoint] 等待 ${_label} ${_host}:${_port} ... (${_i}/${_max})"
    sleep 2
  done
  echo "[entrypoint] 错误：${_max} 次重试后仍无法连接 ${_label} ${_host}:${_port}（请确认 api 与 mysql/redis 在同一 docker compose 网络，且已执行 docker compose up -d）" >&2
  exit 1
}

wait_tcp "MySQL" "$MYSQL_H" "$MYSQL_P" 60
wait_tcp "Redis" "$REDIS_H" "$REDIS_P" 30

exec "$@"
