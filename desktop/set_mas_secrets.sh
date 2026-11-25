#!/bin/sh
# Load the four Mac App Store secrets into this repo's GitHub Actions secret store,
# reading them from a local folder (default ~/Desktop/qs-mas). Nothing is printed
# except the names. The App Store Connect API key is the one set_github_secrets.sh
# already loaded. Run once, then delete the folder.
#
#   sh desktop/set_mas_secrets.sh [folder]
#
# Expects in the folder:
#   app.p12             Apple Distribution certificate with its key (Keychain export)
#   installer.p12       Mac Installer Distribution certificate with its key
#   cert-password.txt   the password chosen at export (the same for both), one line
#   store.provisionprofile   the Mac App Store Connect profile for
#                       ai.myaccessibility.quadstickprofilestudio
set -eu

D="${1:-$HOME/Desktop/qs-mas}"
for f in app.p12 installer.p12 cert-password.txt store.provisionprofile; do
  [ -f "$D/$f" ] || { echo "missing $D/$f" >&2; exit 1; }
done
PW="$(tr -d '\r\n' < "$D/cert-password.txt")"
[ -n "$PW" ] || { echo "cert-password.txt is empty" >&2; exit 1; }

base64 -i "$D/app.p12"                | gh secret set MAS_APP_CERT_P12
base64 -i "$D/installer.p12"          | gh secret set MAS_INSTALLER_CERT_P12
printf '%s' "$PW"                     | gh secret set MAS_CERT_PASSWORD
base64 -i "$D/store.provisionprofile" | gh secret set MAS_PROVISION_PROFILE

echo
gh secret list
echo
echo "All four set. Now delete the folder:  rm -rf \"$D\""
