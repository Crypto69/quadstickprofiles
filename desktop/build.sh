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
    # sign.sh does the real resolving (and refuses an ambiguous match); this is
    # only "is there anything to sign with at all?", so a checkout without a
    # certificate still builds.
    identity="${CODESIGN_IDENTITY:-Developer ID Application}"
    if security find-identity -v -p codesigning | grep -qF "$identity"; then
      sh desktop/sign.sh "desktop/dist/QuadStick Profile Studio.app"
    else
      echo "no codesigning identity matching '$identity' in the keychain: leaving the app unsigned"
    fi
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
