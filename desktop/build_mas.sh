#!/bin/sh
# The Mac App Store build: the same app as build.sh, signed with the App Sandbox
# (sign_mas.sh) and packed as the installer package App Store Connect takes.
#
#   sh desktop/build_mas.sh path/to/profile.provisionprofile
#       -> desktop/dist/QuadStickProfileStudio-<ver>-mas.pkg, ready for upload_mas.sh
#          or Apple's Transporter app. Needs the "Apple Distribution" and the "Mac
#          Installer Distribution" (shown as "3rd Party Mac Developer Installer" on
#          older accounts) certificates in the keychain.
#   sh desktop/build_mas.sh --sandbox-test
#       -> the app in desktop/dist, ad hoc signed in the same sandbox, no package: run
#          scripts/desktop_check.sh --sandboxed on it, or open it and try the drive.
#
# QS_SKIP_BUILD=1 re-signs the app already in desktop/dist instead of building again.
# Needs what build.sh needs (node 22, python 3.12 with the desktop requirements).
set -eu
cd "$(dirname "$0")/.."
MODE="${1:?give the Mac App Store Connect .provisionprofile, or --sandbox-test}"
APP="desktop/dist/QuadStick Profile Studio.app"

eval "$(sh scripts/version.sh)"
# The build number App Store Connect wants to grow with every upload: the commit
# count, which only goes up on main.
QS_BUILD_NUMBER="$(git rev-list --count HEAD 2>/dev/null || echo 1)"
export APP_VERSION QS_BUILD_NUMBER
echo "Mac App Store build $APP_VERSION ($QS_BUILD_NUMBER, $GIT_SHA)"

if [ "${QS_SKIP_BUILD:-}" != 1 ]; then
  (cd web && npm ci --no-audit --no-fund && npm run build)
  printf 'APP_VERSION=%s\nGIT_SHA=%s\nBUILD_TIME=%s\n' "$APP_VERSION" "$GIT_SHA" "$BUILD_TIME" > desktop/version.txt
  python -m PyInstaller --noconfirm --clean desktop/quadstick.spec \
    --distpath desktop/dist --workpath desktop/build
fi
[ -d "$APP" ] || { echo "build_mas.sh: no $APP" >&2; exit 1; }

sh desktop/sign_mas.sh "$APP" "$MODE"
[ "$MODE" = "--sandbox-test" ] && { echo "built $APP (sandbox test)"; exit 0; }

# The installer package is signed with the other certificate. Same rule as the app:
# exactly one match, passed by hash.
IDENTITY="${INSTALLER_IDENTITY:-Installer}"
matches="$(security find-identity -v | grep -E '"(3rd Party Mac Developer Installer|Mac Installer Distribution)' | grep -F "$IDENTITY" || true)"
count="$(printf '%s' "$matches" | grep -c . || true)"
if [ "$count" -ne 1 ]; then
  echo "build_mas.sh: need exactly one Mac Installer Distribution certificate, found $count" >&2
  echo "build_mas.sh: make one in Xcode: Settings > Accounts > Manage Certificates > + > Mac Installer Distribution" >&2
  [ -n "$matches" ] && echo "$matches" >&2
  exit 1
fi
HASH="$(printf '%s\n' "$matches" | sed -n 's/^ *[0-9][0-9]*) \([0-9A-Fa-f]\{40\}\) .*/\1/p')"
out="desktop/dist/QuadStickProfileStudio-${APP_VERSION}-mas.pkg"
rm -f "$out"
productbuild --component "$APP" /Applications --sign "$HASH" "$out"
pkgutil --check-signature "$out"
echo "built $out"
