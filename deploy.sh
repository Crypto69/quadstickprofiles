#!/bin/sh
# Pull latest, rebuild and restart the three containers, stamping the api image
# with the git commit so /api/version shows what is actually running.
#
# Usage, on the NAS:  ./deploy.sh             (pulls main first)
#                     ./deploy.sh --no-pull   (build what is checked out)
#                     ./deploy.sh --force     (skip the in-flight export check)
set -e
cd "$(dirname "$0")"

WEB_PORT="$(sed -n 's/^QS_WEB_PORT=//p' .env 2>/dev/null | tail -1)"
[ -n "$WEB_PORT" ] || WEB_PORT=8324

# The NAS keeps git off the default PATH for non-login shells; look in the
# usual places (add your own, e.g. an App Center install under
# /Volume*/@apps/git/bin), and if all else fails read the commit from .git.
GIT=""
for c in git /usr/bin/git /usr/local/bin/git /opt/bin/git /usr/local/git/bin/git; do
  if command -v "$c" >/dev/null 2>&1; then GIT="$c"; break; fi
done

# On this NAS `git` is often only a shell alias, invisible to scripts. Fall back
# to git inside a throwaway container so pulling still works.
if [ -z "$GIT" ] && command -v docker >/dev/null 2>&1; then
  echo "note: no git binary; using docker alpine/git"
  GIT="docker run --rm -v $(pwd):/repo -w /repo -e HOME=/tmp alpine/git -c safe.directory=/repo"
fi

if [ -n "$GIT" ]; then
  if [ "$1" != "--no-pull" ]; then
    echo "pulling latest..."
    $GIT pull --ff-only
    # TOS share ACLs strip modes on pull. Skip data/: Postgres refuses to
    # start if its data directory is group- or world-readable.
    find . -path ./data -prune -o -print0 2>/dev/null \
      | xargs -0 chmod a+rX 2>/dev/null || true
    chmod +x deploy.sh api/entrypoint.sh 2>/dev/null || true
  fi
fi

# The version stamp (GIT_SHA with -dirty, BUILD_TIME, APP_VERSION as
# <VERSION file>.<commits since it changed>, or the tag on a v* tag) is computed
# by scripts/version.sh, the same script the GitHub workflows and the desktop
# build use. It honours the docker alpine/git fallback through GIT=.
[ -n "$GIT" ] || echo "note: git not found; NOT pulled, commit read from .git (dirty check skipped)"
eval "$(GIT="$GIT" sh scripts/version.sh)"
export GIT_SHA BUILD_TIME APP_VERSION

# Data lives inside the checkout, so it sits on whichever volume the repo was
# cloned onto. Create the folders before compose does, or Docker makes them
# root-owned. Postgres in the Debian postgres:16 image runs as uid 999 (the
# -alpine variant uses 70 -- and the two must never share a data directory,
# see docker-compose.yml).
mkdir -p data/pg data/backups exports
chown 999:999 data/pg 2>/dev/null || true   # no-op unless running as root

# .env must exist: compose reads the db password and ports from it, and a
# missing file silently deploys with the default password.
if [ ! -f .env ]; then
  echo ".env is missing. Copy it and set QS_DB_PASSWORD before deploying:"
  echo "  cp .env.example .env && vi .env"
  exit 1
fi

# Restarting the api container drops any export that is mid-write, and the
# browser is left with a failed download. Cheap check: is the API busy?
# --force skips it when the running request is the thing being fixed.
if [ "$1" != "--force" ] && [ "$2" != "--force" ]; then
  health="$(curl -s --max-time 5 "http://localhost:${WEB_PORT}/api/health" 2>/dev/null || true)"
  case "$health" in
    *'"ok"'*)
      # Anything actively writing into exports/ in the last minute counts as busy.
      busy="$(docker compose exec -T api sh -c \
        'find /app/exports -type f -mmin -1 2>/dev/null | head -5' 2>/dev/null || true)"
      if [ -n "$busy" ]; then
        echo "An export was written in the last minute:"
        echo "$busy"
        echo "Deploying now may interrupt someone mid-download. Wait, or re-run with --force."
        exit 1
      fi
      ;;
    *) : ;;   # not up, or not answering: nothing to interrupt
  esac
fi

echo "building quadstick v${APP_VERSION} ${GIT_SHA} (${BUILD_TIME})"
docker compose build
docker compose up -d

# db and api have health checks; web waits on api. Give them a moment, then say
# what is running rather than claiming success from `up -d` alone.
echo "waiting for the api to come up..."
i=0
while [ $i -lt 60 ]; do
  out="$(curl -s --max-time 3 "http://localhost:${WEB_PORT}/api/version" 2>/dev/null || true)"
  case "$out" in *'"commit"'*) break ;; esac
  i=$((i + 2))
  sleep 2
done
echo "running: ${out:-(not up yet -- docker compose ps; docker compose logs api)}"
docker compose ps
