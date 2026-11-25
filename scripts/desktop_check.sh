#!/bin/sh
# Start a desktop build (or the launcher from a checkout) headless in a throwaway
# home folder, prove it serves the app, the API and an export, then stop it.
#   sh scripts/desktop_check.sh "desktop/dist/QuadStick Profile Studio.app/Contents/MacOS/QuadStick Profile Studio"
#   sh scripts/desktop_check.sh "desktop/dist/QuadStick Profile Studio/QuadStick Profile Studio.exe"
#   sh scripts/desktop_check.sh python desktop/launcher.py
#   sh scripts/desktop_check.sh --sandboxed "desktop/dist/QuadStick Profile Studio.app/Contents/MacOS/QuadStick Profile Studio"
# Used by release.yml after each desktop build, by ci.yml from the checkout, and by
# store-mac.yml on the App Sandbox build (desktop/build_mas.sh --sandbox-test).
#
# --sandboxed: the app may write only inside its container, so the throwaway home is
# a relative QS_DESKTOP_HOME, which the launcher puts under ~ (the container), and
# this script reads it there. It also checks the app said it ran in the sandbox.
set -e
sandboxed=""
if [ "${1:-}" = "--sandboxed" ]; then sandboxed=1; shift; fi
[ $# -ge 1 ] || { echo "usage: $0 [--sandboxed] <command...>"; exit 2; }
out="${TMPDIR:-/tmp}/qs-desktop-check-$$.out"
if [ -n "$sandboxed" ]; then
  plist="$(dirname "$1")/../Info.plist"
  bundle_id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$plist")"
  export QS_DESKTOP_HOME="tmp/qs-desktop-check-$$"
  home="$HOME/Library/Containers/$bundle_id/Data/$QS_DESKTOP_HOME"   # the app makes it
else
  home="${TMPDIR:-/tmp}/qs-desktop-check-$$"
  rm -rf "$home"; mkdir -p "$home"
  export QS_DESKTOP_HOME="$home"
fi

"$@" --headless > "$out" 2>&1 &
pid=$!
trap 'kill $pid 2>/dev/null || true' EXIT

log="$home/logs/launcher.log"
i=0
until grep -q "serving at" "$log" 2>/dev/null; do
  i=$((i+1))
  if [ $i -gt 120 ] || ! kill -0 $pid 2>/dev/null; then
    echo "the app did not start"; cat "$out" 2>/dev/null; cat "$log" 2>/dev/null; exit 1
  fi
  sleep 0.5
done
url="$(sed -n 's/.*serving at \(http[^ ]*\).*/\1/p' "$log" | head -1)"
echo "serving at $url"

fail=0
check() {  # check <label> <path> <expected substring of the response or content-type>
  body="$(curl -s -D "$out.headers" "$url$2")"
  if printf '%s' "$body" | grep -q "$3" || grep -qi "$3" "$out.headers"; then
    echo "ok   $1"
  else
    echo "FAIL $1 ($2): expected '$3'"; fail=1
  fi
}
check "app at /"              "/"                            "<title>"
check "deep link"             "/profiles/2"                  "<title>"
check "api version"           "/api/version"                 '"app_version"'
check "reference card"        "/api/profiles/1/card.html"    "data:image/webp"
check "csv export"            "/api/profiles/1/export.csv"   "text/csv"
check "xlsx export"           "/api/profiles/1/export.xlsx"  "spreadsheetml"
[ -f "$home/exports/ddfortnite.csv" ] && echo "ok   export written to the exports folder" || { echo "FAIL export file missing"; fail=1; }
grep -q "schema: created" "$log" && echo "ok   schema created on first launch" || { echo "FAIL no schema line"; fail=1; }
if [ -n "$sandboxed" ]; then
  grep -q "(App Sandbox)" "$log" && echo "ok   ran inside the App Sandbox" || { echo "FAIL not sandboxed"; fail=1; }
  codesign -d --entitlements - "$(dirname "$1")/../.." 2>/dev/null | grep -q app-sandbox \
    && echo "ok   signed with the App Sandbox entitlement" || { echo "FAIL no sandbox entitlement"; fail=1; }
fi

kill $pid 2>/dev/null || true
wait $pid 2>/dev/null || true
if [ $fail -ne 0 ]; then cat "$out" "$log"; exit 1; fi
rm -rf "$home" "$out" "$out.headers"
echo "desktop check passed"
