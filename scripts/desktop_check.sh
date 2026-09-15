#!/bin/sh
# Start a desktop build (or the launcher from a checkout) headless in a throwaway
# home folder, prove it serves the app, the API and an export, then stop it.
#   sh scripts/desktop_check.sh "desktop/dist/QuadStick Profile Studio.app/Contents/MacOS/QuadStick Profile Studio"
#   sh scripts/desktop_check.sh "desktop/dist/QuadStick Profile Studio/QuadStick Profile Studio.exe"
#   sh scripts/desktop_check.sh python desktop/launcher.py
# Used by release.yml after each desktop build and by ci.yml from the checkout.
set -e
[ $# -ge 1 ] || { echo "usage: $0 <command...>"; exit 2; }
home="${TMPDIR:-/tmp}/qs-desktop-check-$$"
rm -rf "$home"; mkdir -p "$home"
export QS_DESKTOP_HOME="$home"

"$@" --headless > "$home/stdout.txt" 2>&1 &
pid=$!
trap 'kill $pid 2>/dev/null || true' EXIT

log="$home/logs/launcher.log"
i=0
until grep -q "serving at" "$log" 2>/dev/null; do
  i=$((i+1))
  if [ $i -gt 120 ] || ! kill -0 $pid 2>/dev/null; then
    echo "the app did not start"; cat "$home/stdout.txt" 2>/dev/null; cat "$log" 2>/dev/null; exit 1
  fi
  sleep 0.5
done
url="$(sed -n 's/.*serving at \(http[^ ]*\).*/\1/p' "$log" | head -1)"
echo "serving at $url"

fail=0
check() {  # check <label> <path> <expected substring of the response or content-type>
  body="$(curl -s -D "$home/headers.txt" "$url$2")"
  if printf '%s' "$body" | grep -q "$3" || grep -qi "$3" "$home/headers.txt"; then
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

kill $pid 2>/dev/null || true
wait $pid 2>/dev/null || true
if [ $fail -ne 0 ]; then cat "$log"; exit 1; fi
rm -rf "$home"
echo "desktop check passed"
