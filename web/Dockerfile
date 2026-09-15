# Build the SPA, then serve it from nginx with /api proxied to the api container.
FROM node:22-alpine AS build
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# deploy.sh's readable version, shown top-right in the header
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
