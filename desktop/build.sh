#!/bin/sh
# macOS (and Linux) desktop build. From the repo root or anywhere:
#   sh desktop/build.sh            -> desktop/dist/QuadStickProfileStudio-<ver>-macos-<arch>.zip
# Needs: node 22, python 3.12 with `pip install -e core -e api -r desktop/requirements.txt`.
set -e
cd "$(dirname "$0")/.."

eval "$(sh scripts/version.sh)"
export APP_VERSION
echo "building $APP_VERSION ($GIT_SHA, $BUILD_TIME)"

(cd web && npm ci --no-audit --no-fund && npm run build)
printf 'APP_VERSION=%s\nGIT_SHA=%s\nBUILD_TIME=%s\n' "$APP_VERSION" "$GIT_SHA" "$BUILD_TIME" > desktop/version.txt

python -m PyInstaller --noconfirm --clean desktop/quadstick.spec \
  --distpath desktop/dist --workpath desktop/build

case "$(uname -s)" in
  Darwin)
    arch="$(uname -m)"                      # arm64 or x86_64
    out="desktop/dist/QuadStickProfileStudio-${APP_VERSION}-macos-${arch}.zip"
    rm -f "$out"
    # ditto keeps the .app's resource forks and permissions; plain zip does not
    (cd desktop/dist && ditto -c -k --keepParent "QuadStick Profile Studio.app" "$(basename "$out")")
    ;;
  *)
    out="desktop/dist/QuadStickProfileStudio-${APP_VERSION}-linux-$(uname -m).zip"
    rm -f "$out"
    (cd desktop/dist && zip -qr "$(basename "$out")" "QuadStick Profile Studio")
    ;;
esac
echo "built $out"
