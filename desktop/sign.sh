#!/bin/sh
# Code-sign the macOS app bundle for distribution outside the App Store, inside
# out: every Mach-O file first (the Python extension modules, dylibs and the
# launcher executable), then the bundle itself. Hardened runtime plus the
# entitlements next to this script, secure timestamp, so it can be notarised.
#
#   sh desktop/sign.sh "desktop/dist/QuadStick Profile Studio.app"
#
# CODESIGN_IDENTITY selects the certificate: a full name, a substring of one, or
# a 40-character SHA-1 hash. The default matches a "Developer ID Application"
# identity. Whatever it is, it is resolved to exactly one certificate and passed
# to codesign as that certificate's hash — a substring that matches two (say an
# Application and an Installer certificate) makes codesign fail as "ambiguous",
# and a machine with two valid Developer IDs would otherwise sign at random.
set -eu
APP="$1"
HERE="$(cd "$(dirname "$0")" && pwd)"
ENTITLEMENTS="$HERE/entitlements.plist"
IDENTITY="${CODESIGN_IDENTITY:-Developer ID Application}"

# `security find-identity -v -p codesigning` prints one line per valid identity:
#   1) 0123456789ABCDEF0123456789ABCDEF01234567 "Developer ID Application: Name (TEAMID)"
matches="$(security find-identity -v -p codesigning | grep -F "$IDENTITY" || true)"
count="$(printf '%s' "$matches" | grep -c . || true)"
if [ "$count" -eq 0 ]; then
  echo "sign.sh: no codesigning identity in the keychain matches '$IDENTITY'" >&2
  echo "sign.sh: available identities:" >&2
  security find-identity -v -p codesigning >&2
  exit 1
elif [ "$count" -gt 1 ]; then
  echo "sign.sh: '$IDENTITY' matches $count identities; set CODESIGN_IDENTITY to one of them" >&2
  echo "sign.sh: (its full name, or the 40-character hash in the first column)" >&2
  echo "$matches" >&2
  exit 1
fi
HASH="$(printf '%s\n' "$matches" | sed -n 's/^ *[0-9][0-9]*) \([0-9A-Fa-f]\{40\}\) .*/\1/p')"
[ -n "$HASH" ] || { echo "sign.sh: could not read the hash out of: $matches" >&2; exit 1; }
echo "sign.sh: signing with $matches"

sign() {
  codesign --force --timestamp --options runtime \
    --entitlements "$ENTITLEMENTS" --sign "$HASH" "$1"
}

n=0
# Everything Mach-O inside the bundle except the main executable, which is
# signed with the bundle. `file` is the reliable test: .so, .dylib and
# extension-less binaries all appear.
find "$APP/Contents" -type f ! -path "$APP/Contents/MacOS/*" -print0 \
  | xargs -0 file --no-pad \
  | grep 'Mach-O' | cut -d: -f1 \
  | while IFS= read -r f; do sign "$f"; n=$((n+1)); done
sign "$APP"

codesign --verify --deep --strict --verbose=2 "$APP"
echo "sign.sh: signed and verified $APP"
