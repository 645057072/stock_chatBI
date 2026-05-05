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

# MySQL 首次建卷 + 执行 initdb SQL 在 ECS 慢盘上常超过 2 分钟，次数过少会导致 api 先于库就绪而退出
wait_tcp "MySQL" "$MYSQL_H" "$MYSQL_P" 180
wait_tcp "Redis" "$REDIS_H" "$REDIS_P" 45

# 部分 ECS 上：shell 子进程里 socket.connect(主机名) 成功，但 uvicorn 主进程里 getaddrinfo(同一主机名) 持续失败。
# wait_tcp 已证明此刻可解析，这里取出 IPv4 写入环境变量，让 PyMySQL/redis 直连 IP，避开主进程 DNS 差异。
# MySQL/Redis 重建容器后 IP 会变，需一并重启 api（docker compose restart api）。
MYSQL_IPV4=$(python -c "import socket; print(socket.getaddrinfo('$MYSQL_H', int('$MYSQL_P'), socket.AF_INET, socket.SOCK_STREAM)[0][4][0])" 2>/dev/null) || MYSQL_IPV4=""
if [ -n "$MYSQL_IPV4" ]; then
  export CHATBI_MYSQL_HOST="$MYSQL_IPV4"
  export MYSQL_HOST="$MYSQL_IPV4"
  echo "[entrypoint] MySQL 主进程改用 IPv4 ${MYSQL_IPV4}（原主机名 ${MYSQL_H}）"
fi

REDIS_IPV4=$(python -c "import socket; print(socket.getaddrinfo('$REDIS_H', int('$REDIS_P'), socket.AF_INET, socket.SOCK_STREAM)[0][4][0])" 2>/dev/null) || REDIS_IPV4=""
if [ -n "$REDIS_IPV4" ]; then
  export REDIS_IPV4
  export REDIS_P
  _redis_new=$(python -c 'import os, urllib.parse as u
url = os.environ.get("REDIS_URL", "redis://redis:6381/0")
ip = os.environ["REDIS_IPV4"]
p = u.urlparse(url)
netloc = p.netloc or ""
if "@" in netloc:
    print(url)
else:
    port = p.port if p.port is not None else int(os.environ["REDIS_P"])
    path = p.path if p.path else "/0"
    print(f"{p.scheme}://{ip}:{port}{path}")
' 2>/dev/null) || _redis_new=""
  if [ -n "$_redis_new" ]; then
    export REDIS_URL="$_redis_new"
    echo "[entrypoint] Redis 主进程改用 IPv4（原主机名 ${REDIS_H}）"
  fi
fi

exec "$@"
