#!/bin/sh
# Load the five macOS signing secrets into this repo's GitHub Actions secret store,
# reading them from a local folder (default ~/Desktop/qs-signing). Nothing is
# printed except the names. Run once, then delete the folder.
#
#   sh desktop/set_github_secrets.sh [folder]
#
# Expects in the folder:
#   cert.p12            Developer ID Application certificate (Keychain export)
#   cert-password.txt   the password chosen at export, one line
#   AuthKey_<ID>.p8     App Store Connect API key
#   ids.txt             KEY_ID=<ID> and ISSUER_ID=<uuid>, one per line
set -eu

D="${1:-$HOME/Desktop/qs-signing}"
for f in cert.p12 cert-password.txt ids.txt; do
  [ -f "$D/$f" ] || { echo "missing $D/$f" >&2; exit 1; }
done

PW="$(tr -d '\r\n' < "$D/cert-password.txt")"
KEY_ID="$(sed -n 's/^KEY_ID=\(KEY_ID=\)\{0,1\}//p' "$D/ids.txt" | tr -d '\r\n ')"
ISSUER="$(sed -n 's/^ISSUER_ID=//p' "$D/ids.txt" | tr -d '\r\n ')"
P8="$D/AuthKey_$KEY_ID.p8"
[ -n "$PW" ] || { echo "cert-password.txt is empty" >&2; exit 1; }
[ -n "$KEY_ID" ] && [ -n "$ISSUER" ] || { echo "ids.txt needs KEY_ID= and ISSUER_ID=" >&2; exit 1; }
[ -f "$P8" ] || { echo "missing $P8" >&2; exit 1; }

# the workflow base64-decodes the two files; the other three are used as-is
base64 -i "$D/cert.p12" | gh secret set MACOS_CERT_P12
printf '%s' "$PW"       | gh secret set MACOS_CERT_PASSWORD
printf '%s' "$KEY_ID"   | gh secret set APPLE_API_KEY_ID
printf '%s' "$ISSUER"   | gh secret set APPLE_API_ISSUER_ID
base64 -i "$P8"         | gh secret set APPLE_API_KEY_P8

echo
gh secret list
echo
echo "All five set. Now delete the folder:  rm -rf \"$D\""
