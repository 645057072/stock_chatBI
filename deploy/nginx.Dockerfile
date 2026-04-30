# 构建前端 + 生成开发用自签名证书 + Nginx
FROM node:20-alpine AS webbuild
WORKDIR /web
COPY web/package.json ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM nginx:1.27-alpine
RUN apk add --no-cache openssl \
    && mkdir -p /etc/nginx/certs \
    && openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout /etc/nginx/certs/privkey.pem \
        -out /etc/nginx/certs/fullchain.pem \
        -subj "/CN=chatbi-local"

RUN rm -f /etc/nginx/conf.d/default.conf
COPY deploy/nginx.conf /etc/nginx/conf.d/chatbi.conf
COPY --from=webbuild /web/dist /usr/share/nginx/html

EXPOSE 80 443
