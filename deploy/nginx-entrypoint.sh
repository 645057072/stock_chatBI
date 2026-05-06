#!/bin/sh
# 由环境变量生成 Nginx 配置（仅替换占位符，保留 $host 等 Nginx 变量）
set -e
export CHATBI_API_UPSTREAM="${CHATBI_API_UPSTREAM:-api:8000}"
export CHATBI_NGINX_PROXY_TIMEOUT="${CHATBI_NGINX_PROXY_TIMEOUT:-600s}"
envsubst '${CHATBI_API_UPSTREAM} ${CHATBI_NGINX_PROXY_TIMEOUT}' \
  < /etc/nginx/templates/chatbi.conf.template \
  > /etc/nginx/conf.d/chatbi.conf
exec nginx -g 'daemon off;'
