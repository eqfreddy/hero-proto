import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.heroproto.app',
  appName: 'Hero Proto',
  // Points at the compiled SPA — run `npm run build:web` before `npx cap sync`
  webDir: '../app/static/spa',
  // Dev `server.url` is OPT-IN via env so a fresh `npx cap sync` doesn't ship
  // a release APK pointing at localhost. Set CAP_DEV_SERVER=http://10.0.2.2:8000
  // (emulator) or http://<your-lan-ip>:8000 (device) before sync to point the
  // wrap at a local FastAPI. Production builds use capacitor.config.prod.ts.
  ...(process.env.CAP_DEV_SERVER
    ? { server: { url: process.env.CAP_DEV_SERVER, cleartext: true } }
    : {}),
  plugins: {
    PushNotifications: {
      // Android: FCM is wired automatically via google-services.json
      // iOS: ensure Push Notifications capability is on in Xcode
      presentationOptions: ['badge', 'sound', 'alert'],
    },
    StatusBar: {
      style: 'dark',
      backgroundColor: '#0d0d0d',
    },
  },
  android: {
    // Place google-services.json in mobile/android/app/ after `npx cap add android`
    backgroundColor: '#0d0d0d',
  },
  ios: {
    // Place GoogleService-Info.plist in mobile/ios/App/ after `npx cap add ios`
    // iOS builds require macOS + Xcode. Use Codemagic or GitHub mac runners for CI.
    backgroundColor: '#0d0d0d',
    contentInset: 'always',
  },
};

export default config;
