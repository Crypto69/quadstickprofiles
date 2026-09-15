#!/bin/sh
# Notarise the signed macOS app: send the zip to Apple, wait for the verdict,
# staple the ticket onto the .app so Gatekeeper trusts it offline, then rebuild
# the zip (the staple changes the bundle). Needs an App Store Connect API key:
#
#   APPLE_API_KEY_PATH=~/AuthKey_XXXXXXXXXX.p8 APPLE_API_KEY_ID=XXXXXXXXXX \
#   APPLE_API_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
#   sh desktop/notarize.sh "desktop/dist/QuadStick Profile Studio.app" desktop/dist/QuadStickProfileStudio-1.0-macos-arm64.zip
#
# On rejection, prints Apple's log (it names the offending file) and fails.
set -eu
APP="$1"; ZIP="$2"
: "${APPLE_API_KEY_PATH:?}" "${APPLE_API_KEY_ID:?}" "${APPLE_API_ISSUER_ID:?}"
key="--key $APPLE_API_KEY_PATH --key-id $APPLE_API_KEY_ID --issuer $APPLE_API_ISSUER_ID"

# Capture the exit status separately: under `set -e` a failing command
# substitution in a plain assignment would abort here, before Apple's output
# (the whole point of capturing it) had a chance to be printed.
rc=0
out="$(xcrun notarytool submit "$ZIP" $key --wait --timeout 30m 2>&1)" || rc=$?
echo "$out"
id="$(echo "$out" | sed -n 's/^ *id: //p' | head -1)"
if [ "$rc" -ne 0 ] || ! echo "$out" | grep -q '^ *status: Accepted'; then
  [ -n "$id" ] && { xcrun notarytool log "$id" $key || true; }
  echo "notarize.sh: Apple did not accept the app (notarytool exit $rc)" >&2
  exit 1
fi

xcrun stapler staple "$APP"
xcrun stapler validate "$APP"
rm -f "$ZIP"
(cd "$(dirname "$APP")" && ditto -c -k --keepParent "$(basename "$APP")" "$(basename "$ZIP")")
echo "notarize.sh: notarised, stapled and re-zipped $ZIP"
