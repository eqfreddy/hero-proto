import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.heroproto.app',
  appName: 'Hero Proto',
  // Points at the compiled SPA — run `npm run build:web` before `npx cap sync`
  webDir: '../app/static/spa',
  server: {
    url: 'http://10.0.2.2:8000',
    cleartext: true,
  },
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
