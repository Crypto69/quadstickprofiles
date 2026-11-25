#!/bin/sh
# Check the Mac App Store package with Apple, then upload it to App Store Connect,
# with the same App Store Connect API key notarize.sh uses (its role must be App
# Manager or Admin to upload; Developer is enough only to notarise).
#
#   APPLE_API_KEY_PATH=~/AuthKey_XXXXXXXXXX.p8 APPLE_API_KEY_ID=XXXXXXXXXX \
#   APPLE_API_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
#   sh desktop/upload_mas.sh desktop/dist/QuadStickProfileStudio-1.21-mas.pkg [--validate-only]
#
# The build then shows under the app in App Store Connect after Apple has processed
# it (minutes to an hour). Sending it for review is still done there, by hand.
set -eu
PKG="$1"; ONLY="${2:-}"
: "${APPLE_API_KEY_PATH:?}" "${APPLE_API_KEY_ID:?}" "${APPLE_API_ISSUER_ID:?}"
[ -f "$PKG" ] || { echo "upload_mas.sh: no $PKG" >&2; exit 1; }

# altool looks for the key by its ID in ./private_keys or ~/.appstoreconnect/private_keys.
keys="$(mktemp -d)"; trap 'rm -rf "$keys"' EXIT
mkdir -p "$keys/private_keys"
cp "$APPLE_API_KEY_PATH" "$keys/private_keys/AuthKey_$APPLE_API_KEY_ID.p8"
cd "$keys"
pkg="$(cd "$OLDPWD" && cd "$(dirname "$PKG")" && pwd)/$(basename "$PKG")"
auth="--apiKey $APPLE_API_KEY_ID --apiIssuer $APPLE_API_ISSUER_ID"

xcrun altool --validate-app -f "$pkg" -t macos $auth
echo "upload_mas.sh: Apple accepted the package's checks"
[ "$ONLY" = "--validate-only" ] && exit 0
xcrun altool --upload-app -f "$pkg" -t macos $auth
echo "upload_mas.sh: uploaded $pkg"
