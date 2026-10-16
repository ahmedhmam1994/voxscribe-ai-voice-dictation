#!/usr/bin/env bash
# Installs the debug APK on the connected phone and brings VoxScribe's
# accessibility service back to life.
#
# Android leaves the service switched on but disconnected, and often marks it
# as crashed, after every reinstall. The floating button then never appears
# because the service no longer receives events. Switching only VoxScribe's
# entry off and on again fixes it, but a short pause is not enough: this waits,
# then CHECKS with dumpsys that the service is bound and not listed as crashed,
# and repeats the toggle until it is (or says plainly that it is not). Other
# accessibility services are left exactly as they are.
#
# Run from the Flutter project root after `flutter build apk --debug`.
set -euo pipefail

export MSYS_NO_PATHCONV=1
ADB="${ADB:-adb}"
APK="build/app/outputs/flutter-apk/app-debug.apk"
PACKAGE="com.voxscribe.android"
SERVICE="$PACKAGE/$PACKAGE.VoxScribeAccessibilityService"
# Android saves the entry in either form, depending on how it was switched on.
SHORT_SERVICE="$PACKAGE/.VoxScribeAccessibilityService"
SETTING="enabled_accessibility_services"

"$ADB" install -r "$APK"

service_ok() {
  local report
  report="$("$ADB" shell dumpsys accessibility | tr -d '\r')"
  # Bound means connected; it must not be on the crashed list either.
  grep -q "label=VoxScribe" <<<"$report" || return 1
  grep "Crashed services" <<<"$report" | grep -q "$PACKAGE" && return 1
  return 0
}

enabled="$("$ADB" shell settings get secure "$SETTING" | tr -d '\r')"
if [[ "$enabled" != *"$SERVICE"* && "$enabled" != *"$SHORT_SERVICE"* ]]; then
  echo "VoxScribe is not enabled in Accessibility yet. Turn it on once by hand."
else
  others="$(printf '%s' "$enabled" | tr ':' '\n' | grep -vxF -e "$SERVICE" -e "$SHORT_SERVICE" | paste -sd: - || true)"
  for attempt in 1 2 3; do
    if [[ -n "$others" ]]; then
      "$ADB" shell settings put secure "$SETTING" "$others"
    else
      "$ADB" shell settings delete secure "$SETTING"
    fi
    sleep 3
    "$ADB" shell settings put secure "$SETTING" "$enabled"
    sleep 4
    if service_ok; then
      echo "Accessibility service connected (attempt $attempt)."
      break
    fi
    echo "Accessibility service not connected yet (attempt $attempt)."
    if [[ "$attempt" == 3 ]]; then
      echo "WARNING: still not connected. Turn VoxScribe off and on in Accessibility settings."
      exit 1
    fi
  done
fi

"$ADB" shell am start -n "$PACKAGE/.MainActivity"
