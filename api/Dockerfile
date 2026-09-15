FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
# build context is the repo root so both packages are available
COPY core /app/core
COPY api /app/api
COPY fixtures /app/fixtures
COPY actions /app/actions
RUN pip install -e /app/core && pip install -e "/app/api[postgres]"
WORKDIR /app/api
ENV QS_FIXTURES_DIR=/app/fixtures QS_ACTIONS_DIR=/app/actions QS_EXPORTS_DIR=/app/exports
# Stamped by deploy.sh so /api/version reports the commit that was built.
ARG GIT_SHA=unknown
ARG BUILD_TIME=unknown
ARG APP_VERSION=dev
ENV QS_GIT_SHA=$GIT_SHA QS_BUILD_TIME=$BUILD_TIME QS_APP_VERSION=$APP_VERSION
EXPOSE 8000
ENTRYPOINT ["/app/api/entrypoint.sh"]
