# 构建前端 + 生成开发用自签名证书 + Nginx
FROM node:20-alpine AS webbuild
WORKDIR /web
# 国内构建默认 npmmirror，避免 registry.npmjs.org 超时（可通过 NPM_REGISTRY 构建参数改为官方源）
ARG NPM_REGISTRY=https://registry.npmmirror.com
# 与浏览器请求前缀一致；compose build.args 可由根目录 .env 注入 VITE_API_PREFIX
ARG VITE_API_PREFIX=/api
ENV VITE_API_PREFIX=$VITE_API_PREFIX
RUN npm config set registry "${NPM_REGISTRY}"
COPY web/package.json ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM nginx:1.27-alpine
# curl 用于 compose healthcheck；openssl 用于本地自签名 HTTPS
RUN apk add --no-cache openssl curl gettext \
    && mkdir -p /etc/nginx/certs /etc/nginx/templates \
    && openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout /etc/nginx/certs/privkey.pem \
        -out /etc/nginx/certs/fullchain.pem \
        -subj "/CN=chatbi-local"

RUN rm -f /etc/nginx/conf.d/default.conf
COPY deploy/nginx.conf.template /etc/nginx/templates/chatbi.conf.template
COPY deploy/nginx-entrypoint.sh /docker-entrypoint-nginx.sh
RUN chmod +x /docker-entrypoint-nginx.sh
COPY --from=webbuild /web/dist /usr/share/nginx/html

EXPOSE 80 443
ENTRYPOINT ["/docker-entrypoint-nginx.sh"]
