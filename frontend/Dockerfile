# frontend/Dockerfile - Vue3 生产构建 + Nginx 静态服务
# 阶段 1：构建（npm ci 按 package-lock.json 精确安装）
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# 阶段 2：Nginx 提供静态文件 + API 反代
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
