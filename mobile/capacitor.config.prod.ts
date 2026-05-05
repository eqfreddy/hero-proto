import { CapacitorConfig } from '@capacitor/cli';

// Production Capacitor config — used for store-bound builds.
// The SPA is bundled (no `server.url`), API calls go to the absolute
// VITE_API_BASE_URL baked in at build time.
//
// To use:
//   1. Build SPA with: VITE_API_BASE_URL="https://hero-proto.fly.dev" npm run build --prefix ../frontend
//   2. Swap configs: cp capacitor.config.prod.ts capacitor.config.ts (or symlink)
//   3. npx cap sync android && open in Android Studio for a release bundle.
//
// Or use the helper: bash mobile/build-prod-android.sh

const config: CapacitorConfig = {
  appId: 'com.heroproto.app',
  appName: 'Hero Proto',
  webDir: '../app/static/spa',
  // No server.url → bundled webDir is loaded from file://
  plugins: {
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
    StatusBar: {
      style: 'dark',
      backgroundColor: '#0d0d0d',
    },
  },
  android: {
    backgroundColor: '#0d0d0d',
  },
  ios: {
    backgroundColor: '#0d0d0d',
    contentInset: 'always',
  },
};

export default config;
