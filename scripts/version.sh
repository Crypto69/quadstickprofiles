#!/bin/sh
# The one place the version stamp is computed. deploy.sh (NAS), the GitHub
# workflows and the desktop build all use it. Prints three KEY=value lines:
#
#   APP_VERSION  on a v* tag (GITHUB_REF_NAME in Actions, or the tag at HEAD)
#                the tag without the v, e.g. v1.7 -> 1.7; otherwise
#                <VERSION file>.<commits since VERSION last changed>, so every
#                deployed commit gets its own number without anyone editing
#                anything, and bumping VERSION to 2 starts 2.0. Without git only
#                the major is known.
#   GIT_SHA      short commit, "-dirty" when the tree has uncommitted changes,
#                "unknown" without git.
#   BUILD_TIME   UTC, minute precision.
#
# Usage:  eval "$(sh scripts/version.sh)"        (from the repo root)
#         GIT="docker run ... alpine/git" sh scripts/version.sh   (deploy.sh's fallback)
# Runs from any directory; resolves the repo root from its own location.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

if [ -z "$GIT" ] && command -v git >/dev/null 2>&1; then GIT=git; fi

GIT_SHA=unknown
if [ -n "$GIT" ]; then
  GIT_SHA="$($GIT rev-parse --short=7 HEAD 2>/dev/null || echo unknown)"
  if [ "$GIT_SHA" != unknown ] && [ -n "$($GIT status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    GIT_SHA="${GIT_SHA}-dirty"
  fi
elif [ -f .git/HEAD ]; then
  ref="$(sed -n 's/^ref: //p' .git/HEAD)"
  if [ -n "$ref" ] && [ -f ".git/$ref" ]; then full="$(cat ".git/$ref")"
  elif [ -n "$ref" ] && [ -f .git/packed-refs ]; then full="$(grep " $ref\$" .git/packed-refs | cut -d' ' -f1)"
  else full="$(cat .git/HEAD)"; fi
  GIT_SHA="$(printf '%s' "$full" | cut -c1-7)"
  [ -n "$GIT_SHA" ] || GIT_SHA=unknown
fi

BUILD_TIME="$(date -u +%Y-%m-%dT%H:%MZ)"

tag=""
if [ "$GITHUB_REF_TYPE" = tag ]; then tag="$GITHUB_REF_NAME"
elif [ -n "$GIT" ]; then tag="$($GIT describe --tags --exact-match HEAD 2>/dev/null || true)"; fi

case "$tag" in
  v[0-9]*) APP_VERSION="${tag#v}" ;;
  *)
    MAJOR="$(tr -d '[:space:]' < VERSION 2>/dev/null)"
    [ -n "$MAJOR" ] || MAJOR=0
    if [ -n "$GIT" ]; then
      since="$($GIT log -n1 --format=%H -- VERSION 2>/dev/null)"
      minor="$([ -n "$since" ] && $GIT rev-list --count "${since}..HEAD" 2>/dev/null)"
      APP_VERSION="${MAJOR}.${minor:-0}"
    else
      APP_VERSION="${MAJOR}"
    fi ;;
esac

printf 'APP_VERSION=%s\nGIT_SHA=%s\nBUILD_TIME=%s\n' "$APP_VERSION" "$GIT_SHA" "$BUILD_TIME"
