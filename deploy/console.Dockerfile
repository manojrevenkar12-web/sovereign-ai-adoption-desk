# The console, served by nginx, with /api proxied to the desk API.
FROM node:22-alpine AS build
WORKDIR /web
COPY web/package.json web/package-lock.json web/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY web ./
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/console-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 8081
