#!/bin/sh
# 由环境变量生成 Nginx 配置（仅替换占位符，保留 $host 等 Nginx 变量）
set -e
# Windows 编辑 .env 可能带入 \r；空值会导致 proxy_pass http:// 非法
CHATBI_API_UPSTREAM=$(printf '%s' "${CHATBI_API_UPSTREAM:-api:8000}" | tr -d '\r')
CHATBI_NGINX_PROXY_TIMEOUT=$(printf '%s' "${CHATBI_NGINX_PROXY_TIMEOUT:-600s}" | tr -d '\r')
CHATBI_API_UPSTREAM=$(printf '%s' "$CHATBI_API_UPSTREAM" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
if [ -z "$CHATBI_API_UPSTREAM" ]; then
  CHATBI_API_UPSTREAM=api:8000
fi
export CHATBI_API_UPSTREAM CHATBI_NGINX_PROXY_TIMEOUT
envsubst '${CHATBI_API_UPSTREAM} ${CHATBI_NGINX_PROXY_TIMEOUT}' \
  < /etc/nginx/templates/chatbi.conf.template \
  > /etc/nginx/conf.d/chatbi.conf
exec nginx -g 'daemon off;'
