#!/bin/sh
# Sign the macOS app for the Mac App Store, inside out, with the App Sandbox
# (mas.entitlements.plist). Two ways:
#
#   sh desktop/sign_mas.sh "desktop/dist/QuadStick Profile Studio.app" path/to/profile.provisionprofile
#       For the store: the "Mac App Store Connect" provisioning profile for
#       ai.myaccessibility.quadstickprofilestudio is copied in as
#       Contents/embedded.provisionprofile, its application and team identifiers are
#       added to the entitlements, and everything is signed with the "Apple
#       Distribution" certificate (CODESIGN_IDENTITY picks another, as in sign.sh).
#       A store-signed app does not open outside the store, so test with the next form.
#
#   sh desktop/sign_mas.sh "desktop/dist/QuadStick Profile Studio.app" --sandbox-test
#       Same entitlements without the identifiers, signed ad hoc: the very same
#       sandbox, on this Mac, with no certificate. scripts/desktop_check.sh runs it.
#
# No hardened runtime: the store does not need it, and CPython would need the two
# exceptions entitlements.plist carries for the Developer ID build.
set -eu
APP="$1"; MODE="${2:?give a .provisionprofile, or --sandbox-test}"
HERE="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist")"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
ent="$work/app.entitlements"
cp "$HERE/mas.entitlements.plist" "$ent"

if [ "$MODE" = "--sandbox-test" ]; then
  HASH="-"
  rm -f "$APP/Contents/embedded.provisionprofile"
  echo "sign_mas.sh: ad hoc, App Sandbox only (a test build; it cannot be uploaded)"
else
  PROFILE="$MODE"
  [ -f "$PROFILE" ] || { echo "sign_mas.sh: no provisioning profile at $PROFILE" >&2; exit 1; }
  security cms -D -i "$PROFILE" > "$work/profile.plist"
  pget() { /usr/libexec/PlistBuddy -c "Print :$1" "$work/profile.plist"; }
  APPID="$(pget 'Entitlements:com.apple.application-identifier')"
  TEAM="$(pget 'Entitlements:com.apple.developer.team-identifier')"
  # The profile must be the store one for this app: not a development profile (it
  # would carry ProvisionedDevices), not another app's, and not expired.
  [ "$APPID" = "$TEAM.$BUNDLE_ID" ] || {
    echo "sign_mas.sh: the profile is for $APPID, the app is $TEAM.$BUNDLE_ID" >&2; exit 1; }
  if pget ProvisionedDevices > /dev/null 2>&1; then
    echo "sign_mas.sh: that is a development profile; use the Mac App Store Connect one" >&2; exit 1
  fi
  expires="$(plutil -extract ExpirationDate raw -o - "$work/profile.plist")"     # 2027-08-08T11:38:18Z
  if [ "$(date -j -u -f '%Y-%m-%dT%H:%M:%SZ' "$expires" +%s 2>/dev/null || echo 0)" -lt "$(date +%s)" ]; then
    echo "sign_mas.sh: the profile expired ($expires); download a new one" >&2; exit 1
  fi
  /usr/libexec/PlistBuddy -c "Add :com.apple.application-identifier string $APPID" "$ent"
  /usr/libexec/PlistBuddy -c "Add :com.apple.developer.team-identifier string $TEAM" "$ent"
  cp "$PROFILE" "$APP/Contents/embedded.provisionprofile"

  # The same one-certificate rule as sign.sh: resolved to one hash, or stop.
  IDENTITY="${CODESIGN_IDENTITY:-Apple Distribution}"
  matches="$(security find-identity -v -p codesigning | grep -F "$IDENTITY" || true)"
  count="$(printf '%s' "$matches" | grep -c . || true)"
  if [ "$count" -ne 1 ]; then
    echo "sign_mas.sh: '$IDENTITY' matches $count codesigning identities; set CODESIGN_IDENTITY to one" >&2
    security find-identity -v -p codesigning >&2
    exit 1
  fi
  HASH="$(printf '%s\n' "$matches" | sed -n 's/^ *[0-9][0-9]*) \([0-9A-Fa-f]\{40\}\) .*/\1/p')"
  printf '%s\n' "$matches" | grep -q "($TEAM)" || {
    echo "sign_mas.sh: $matches is not from team $TEAM, the profile's team" >&2; exit 1; }
  echo "sign_mas.sh: signing for the Mac App Store with $matches"
fi

# A helper executable would need its own two entitlements (app-sandbox + inherit);
# the PyInstaller bundle has none besides the main one, so stop if that changes.
inherit="$work/inherit.entitlements"
cat > "$inherit" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>com.apple.security.app-sandbox</key><true/>
  <key>com.apple.security.inherit</key><true/>
</dict></plist>
EOF

ts="--timestamp"; [ "$HASH" = "-" ] && ts=""
find "$APP/Contents" -type f ! -path "$APP/Contents/MacOS/*" -print0 \
  | xargs -0 file --no-pad | grep 'Mach-O' > "$work/machos" || true
while IFS= read -r line; do
  f="${line%%: Mach-O*}"
  case "$line" in
    *executable*) codesign --force $ts --entitlements "$inherit" --sign "$HASH" "$f" ;;
    *)            codesign --force $ts --sign "$HASH" "$f" ;;
  esac
done < "$work/machos"
codesign --force $ts --entitlements "$ent" --sign "$HASH" "$APP"

codesign --verify --deep --strict --verbose=2 "$APP"
codesign -d --entitlements - "$APP" 2>/dev/null | grep -q 'com.apple.security.app-sandbox' || {
  echo "sign_mas.sh: the signed app has no App Sandbox entitlement" >&2; exit 1; }
echo "sign_mas.sh: signed $APP ($(wc -l < "$work/machos" | tr -d ' ') nested files)"
