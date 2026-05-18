# Android field test — 2026-05-17

**Build:** `adf1026` (versionCode 164, versionName 1.0.164)
**Device:** Pixel 10 Pro emulator (1280×2856, API 35)
**APK:** `mobile/android/app/build/outputs/apk/debug/app-debug.apk` — 14 MB

## Result: PASS (build healthy, lobby + auth verified)

## Verified

- ✅ `mobile/build-prod-android.sh` completes; SPA bundled at `app-debug.apk` / `assets/public/`
- ✅ Capacitor sync places `index.html`, `assets/`, `battle-3d/`, `sw.js`, `manifest.webmanifest` correctly
- ✅ `./gradlew assembleDebug` succeeds in 1m 17s (194 tasks, 94 executed)
- ✅ APK installs without permission issues (INTERNET + POST_NOTIFICATIONS only)
- ✅ App launches to login screen with full cyberpunk styling
- ✅ Status bar dark, no system-bar overlap
- ✅ Version tag `vadf1026` visible bottom-right
- ✅ Auth via JWT works (registered via API, injected via CDP localStorage)
- ✅ Desktop lobby renders inside webview — toned cream/gold palette, topbar player + currencies, ticker, featured hero panel (DevOps Apprentice with full stats), DEPLOY button, daily quest queue with progress bars
- ✅ Network/CORS clean; no errors aside from a missing favicon.ico (cosmetic)

## Known issue caught during testing

**Hard-navigation breaks Capacitor relative asset paths.**

Setting `window.location.href = '/app/lobby'` (or any client-side hard nav) causes
the bundled SPA's relative `./assets/index-*.js` to resolve against the new path
→ `https://localhost/app/assets/...` → 404 → blank screen.

Normal in-app routing via React Router is fine (no page reload). The bug only
bites if a push-notification deep link, custom URL scheme, or external link
triggers a hard nav to a sub-path.

**Fix candidates** (defer; not a launch blocker):
1. Switch Vite `base` from `/app/` to `./` for the production-Android build
2. Add a Capacitor `appendUserAgent` + URL rewrite rule in `MainActivity` to
   strip `/app` prefix from sub-paths and let SPA routing handle it
3. Document that all deep-link entries must hit `/` and let the SPA route

## Not visually verified (next-session checklist)

- [ ] Bottom nav stays above gesture bar across screen sizes
- [ ] Back button behavior (Capacitor default: close app; check whether app
      handles back through React Router on multi-page paths)
- [ ] Shop tab SKU filtering on native (Stripe products must be hidden on iOS
      per S1009 — only Apple StoreKit on iOS, Stripe on Android allowed)
- [ ] Battle Pass purchase messaging in native context
- [ ] Dashboard monetization prompts behavior
- [ ] Battle 3D mounts on emulator (GPU profile may differ from real device)
- [ ] Action bar (Attack/Skill/Limit/Defend) touch targets on small phones
- [ ] Quip floating text doesn't overflow narrow viewport
- [ ] Turn-order ribbon ergonomics on portrait orientation

## Layout observation

The new lobby is responsive but defaults to its desktop layout above 1024px
and collapses to single-column below. On the Pixel 10 Pro's 1280px wide
viewport (in vertical orientation it renders narrower due to safe-area
inset), the layout falls into mobile mode — sidenav becomes a horizontal
chip strip at the bottom and the aside (roster/BP/events/guild) stacks
below main. This is the intended behavior but worth a manual eyeball pass
on a real phone — the desktop-first design may want a third breakpoint
between phone-portrait and tablet-landscape.

## Reproduce

```
# 1. Build APK
cd /c/Users/User/.claude/mmorpg/hero-proto
bash mobile/build-prod-android.sh
cd mobile/android && ANDROID_VERSION_CODE=164 ANDROID_VERSION_NAME=1.0.164 ./gradlew.bat assembleDebug

# 2. Boot emulator
"$ANDROID_HOME/emulator/emulator.exe" -avd Pixel_10_Pro -no-snapshot-load

# 3. Install + launch
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell monkey -p com.heroproto.app -c android.intent.category.LAUNCHER 1

# 4. Auth shortcut (CDP injection)
adb forward tcp:9222 localabstract:webview_devtools_remote_<PID>
# JWT obtained via /auth/register API, injected:
#   localStorage.setItem("heroproto_jwt", "<jwt>")
#   window.location.replace("/")
```
