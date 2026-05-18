# Android field test — 2026-05-17

**Build:** `adf1026` (versionCode 164, versionName 1.0.164)
**Device:** Pixel 10 Pro emulator (1280×2856 physical, DPR ~3.5 → ~366 CSS px wide, API 35)
**APK:** `mobile/android/app/build/outputs/apk/debug/app-debug.apk` — 14 MB

## Result: PARTIAL

Build chain, install, launch, and lobby render verified. **Battle UX (Phases A–E
— action bar, damage numbers, quips, synergy chip, turn-order ribbon) was not
exercised on device** — the DEPLOY-button tap didn't register and I stopped
investigating rather than burn more context on coordinate-tuning. Treat this
as "the bundle is healthy" not "the new combat works on Android."

## Verified

- ✅ `mobile/build-prod-android.sh` completes; SPA bundles into
  `mobile/android/app/src/main/assets/public/` via Capacitor sync, which then
  ends up packaged inside the APK at build time
- ✅ Capacitor places `index.html`, `assets/`, `battle-3d/`, `sw.js`,
  `manifest.webmanifest` correctly
- ✅ `./gradlew assembleDebug` succeeds in 1m 17s (194 actionable tasks: 94
  executed, 100 up-to-date)
- ✅ APK installs without prompts; permissions limited to INTERNET +
  POST_NOTIFICATIONS
- ✅ App launches to login screen with full cyberpunk styling
- ✅ Status bar dark; no system-bar overlap on the rendered web content
- ✅ Version tag `vadf1026` visible bottom-right of the login screen
- ✅ Desktop lobby renders inside the webview when authed — toned cream/gold
  palette, topbar with player + currencies, ticker, featured-hero panel
  (DevOps Apprentice with full stats), DEPLOY button, daily quest queue with
  progress bars
- ✅ Network traffic clean from inside the webview; the only 404 is
  `/favicon.ico` (cosmetic)

## Verified narrowly (caveats)

- **Auth.** Confirmed via API: registered through
  `POST /auth/register` against the live Fly API, then injected the JWT into
  `localStorage["heroproto_jwt"]` over the Chrome DevTools Protocol bridge,
  then `window.location.replace("/")`. The **in-app sign-in form was NOT
  driven end-to-end** — my `adb shell input tap` coordinates failed to focus
  the email field (placeholder text persisted across attempts), so the
  actual UX path of "type email + password → tap Sign in" is untested on
  Android. Re-test on a real device.

## Not verified — next-session checklist

- [ ] In-app sign-in form (tap field → keyboard → submit) on real touch
- [ ] Battle 3D mounts on emulator/device (GPU profile differs from desktop)
- [ ] Action bar (Attack / Skill / Limit / Defend) touch targets on small
      phones — the buttons render at 480-640 px min-width in CSS; need to
      check they don't overflow at 360 CSS px
- [ ] Floating damage numbers + quip toasts position correctly when the
      webview is narrower than the desktop reference
- [ ] Turn-order ribbon legibility in portrait orientation
- [ ] Faction synergy chip wraps gracefully at narrow widths
- [ ] Bottom nav stays above gesture bar across screen sizes
- [ ] Back button behavior (Capacitor default closes the app; SPA may need
      `App.addListener('backButton', ...)` to do React Router back navigation
      instead)
- [ ] Shop tab SKU filtering on native (Stripe products must be hidden on
      iOS per S1009; Android shows Stripe)
- [ ] Battle Pass purchase messaging in native context
- [ ] Dashboard monetization prompts behavior

## Known issue caught during testing

**Hard-navigation to a sub-path breaks Capacitor relative asset resolution.**

Setting `window.location.href = '/app/lobby'` (or any client-side hard nav to
a path other than `/`) causes the bundled SPA's relative
`./assets/index-*.js` references to resolve against the new path —
`https://localhost/app/lobby` + `./assets/index-*.js` →
`https://localhost/app/assets/index-*.js` → 404 → blank screen.

Capacitor's SPA fallback serves the same `index.html` for unknown paths, but
the HTML's relative asset paths only work when served at root.

Normal in-app routing via React Router (`navigate('/app/lobby')`) is
unaffected — those changes are pushState only and don't reload the page.
The bug only bites entry paths: push-notification deep links, custom URL
schemes, or external links targeting any sub-path.

**Fix candidates** (defer; not a launch blocker since no current entry uses
sub-path deep links):

1. Post-process the mobile `index.html` to rewrite `./assets/…` to absolute
   `/assets/…`. Vite base stays `/app/static/spa/` for desktop; the mobile
   build script does the rewrite after `cap sync`.
2. Add `<base href="/">` to the mobile `index.html` so relative paths
   resolve from root regardless of the current URL.
3. Intercept sub-path loads in `MainActivity` and rewrite them to load the
   root index then push the intended route through Capacitor's bridge.
4. Document that all deep-link entry points must hit `/` and let the SPA
   route internally.

## Layout observation

The new lobby is responsive — desktop layout above 1024 CSS px, single-column
stack below. The Pixel 10 Pro's physical 1280 px ÷ DPR ~3.5 = **~366 CSS px**,
deep into mobile breakpoint territory. As designed, the sidenav becomes a
horizontal chip strip and the aside (roster / BP / events / guild) stacks
below main. Intended behavior, but the desktop-first design probably wants
a third breakpoint between phone-portrait (~360-440) and full-desktop
(≥1024) — tablet-landscape (~768-1023) currently falls into the same
mobile stack and may want its own layout.

## Reproduce

```bash
# 1. Build APK
cd /c/Users/User/.claude/mmorpg/hero-proto
bash mobile/build-prod-android.sh
cd mobile/android && ANDROID_VERSION_CODE=164 ANDROID_VERSION_NAME=1.0.164 \
  ./gradlew.bat assembleDebug

# 2. Boot emulator
"$ANDROID_HOME/emulator/emulator.exe" -avd Pixel_10_Pro -no-snapshot-load

# 3. Install + launch
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell monkey -p com.heroproto.app -c android.intent.category.LAUNCHER 1

# 4. (optional) Auth shortcut via Chrome DevTools Protocol
#    Find the live webview PID and forward its devtools socket:
PID=$(adb shell cat /proc/net/unix | grep webview_devtools_remote | \
  awk '{print $NF}' | sed 's/@webview_devtools_remote_//')
adb forward tcp:9222 localabstract:webview_devtools_remote_$PID
#    Then via the CDP WebSocket (suppress_origin=True required):
#      localStorage.setItem("heroproto_jwt", "<jwt>")
#      window.location.replace("/")
```
