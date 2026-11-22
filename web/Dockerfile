# Build the SPA, then serve it from nginx with /api proxied to the api container.
# The SPA is plain files, the same on every CPU, so it is built once on the
# builder's own platform: the release's arm64 image would otherwise run npm and
# vite under QEMU emulation, which is slow and has hung a release build.
FROM --platform=$BUILDPLATFORM node:22-alpine AS build
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# deploy.sh's readable version, shown top-right in the header
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION
RUN npm run build

# The stable line, unpinned: each build picks up its latest patch release
# (deploy.sh builds with --pull, so a cached older copy is never reused).
FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
