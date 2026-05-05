var _a, _b;
// frontend/vite.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { execSync } from 'node:child_process';
function gitShort() {
    try {
        return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
    }
    catch (_a) {
        return 'dev';
    }
}
var BUILD_VERSION = (_a = process.env.VITE_APP_VERSION) !== null && _a !== void 0 ? _a : gitShort();
var BUILD_TIME = (_b = process.env.VITE_APP_BUILD_TIME) !== null && _b !== void 0 ? _b : new Date().toISOString().replace('T', ' ').slice(0, 19) + 'Z';
export default defineConfig({
    define: {
        __APP_VERSION__: JSON.stringify(BUILD_VERSION),
        __APP_BUILD_TIME__: JSON.stringify(BUILD_TIME),
    },
    plugins: [
        react(),
        VitePWA({
            registerType: 'autoUpdate',
            manifest: {
                name: 'hero-proto',
                short_name: 'hero-proto',
                theme_color: '#0b0d10',
                background_color: '#0b0d10',
                display: 'standalone',
                start_url: '/app/',
                scope: '/app/',
                icons: [
                    { src: '/app/static/icons/hero-proto-192.png', sizes: '192x192', type: 'image/png' },
                    { src: '/app/static/icons/hero-proto-512.png', sizes: '512x512', type: 'image/png' },
                    { src: '/app/static/icons/hero-proto-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
                ],
            },
        }),
    ],
    base: '/app/static/spa/',
    build: {
        outDir: '../app/static/spa',
        emptyOutDir: true,
    },
    server: {
        port: 5173,
        proxy: {
            '/me': 'http://localhost:8000',
            '/heroes': 'http://localhost:8000',
            '/battles': 'http://localhost:8000',
            '/raids': 'http://localhost:8000',
            '/guilds': 'http://localhost:8000',
            '/stages': 'http://localhost:8000',
            '/summon': 'http://localhost:8000',
            '/shop': 'http://localhost:8000',
            '/arena': 'http://localhost:8000',
            '/friends': 'http://localhost:8000',
            '/dm': 'http://localhost:8000',
            '/daily': 'http://localhost:8000',
            '/story': 'http://localhost:8000',
            '/achievements': 'http://localhost:8000',
            '/events': 'http://localhost:8000',
            '/crafting': 'http://localhost:8000',
            '/notifications': 'http://localhost:8000',
            '/announcements': 'http://localhost:8000',
            '/liveops': 'http://localhost:8000',
            '/auth': 'http://localhost:8000',
            '/placeholder': 'http://localhost:8000',
            '/gear': 'http://localhost:8000',
            '/inventory': 'http://localhost:8000',
            '/admin': { target: 'http://localhost:8000', rewrite: function (p) { return p; } },
        },
    },
    test: {
        environment: 'jsdom',
        setupFiles: ['./src/test/setup.ts'],
        globals: true,
    },
});
