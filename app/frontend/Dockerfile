# Stage 1: Build
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Serve via nginx
FROM nginx:1.31-alpine
RUN apk add --no-cache openssl
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY tls.conf /etc/nginx/easm-tls.conf
COPY docker-entrypoint.d/40-easm-tls.sh /docker-entrypoint.d/40-easm-tls.sh
RUN chmod +x /docker-entrypoint.d/40-easm-tls.sh
