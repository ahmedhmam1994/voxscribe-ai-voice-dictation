#!/usr/bin/env bash
# Installs the debug APK on the connected phone and reconnects VoxScribe's
# accessibility service. Android leaves the service switched on but
# disconnected after every reinstall; switching only VoxScribe's entry off and
# on again brings it back without touching the phone. Other accessibility
# services are left exactly as they are.
#
# Run from the Flutter project root after `flutter build apk --debug`.
set -euo pipefail

export MSYS_NO_PATHCONV=1
ADB="${ADB:-adb}"
APK="build/app/outputs/flutter-apk/app-debug.apk"
SERVICE="com.voxscribe.android/com.voxscribe.android.VoxScribeAccessibilityService"
SETTING="enabled_accessibility_services"

"$ADB" install -r "$APK"

enabled="$("$ADB" shell settings get secure "$SETTING" | tr -d '\r')"
if [[ "$enabled" == *"$SERVICE"* ]]; then
  others="$(printf '%s' "$enabled" | tr ':' '\n' | grep -vxF "$SERVICE" | paste -sd: - || true)"
  if [[ -n "$others" ]]; then
    "$ADB" shell settings put secure "$SETTING" "$others"
  else
    "$ADB" shell settings delete secure "$SETTING"
  fi
  sleep 1
  "$ADB" shell settings put secure "$SETTING" "$enabled"
  echo "Accessibility service reconnected."
else
  echo "VoxScribe is not enabled in Accessibility yet. Turn it on once by hand."
fi

"$ADB" shell am start -n com.voxscribe.android/.MainActivity
