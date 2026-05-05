/**
 * Capacitor push-notification bootstrap.
 *
 * Call `initPush()` once after the user is logged in (e.g. in Shell.tsx after
 * the /me query resolves). It's a no-op in the browser — Capacitor's plugin
 * detects the web platform and skips silently.
 *
 * Flow:
 *  1. Request permission
 *  2. On registration → POST /notifications/device-token with the FCM/APNs token
 *  3. On foreground message → dispatch a browser CustomEvent so toast/bell can react
 */

import { apiFetch, apiPost } from './client'

type PushPlugin = {
  requestPermissions: () => Promise<{ receive: string }>
  register: () => Promise<void>
  addListener: (event: string, cb: (data: unknown) => void) => Promise<{ remove: () => void }>
}

function getPlugin(): PushPlugin | null {
  // @capacitor/push-notifications is only available in a native context.
  // In the browser the import resolves but the plugin is a web stub.
  try {
    // Dynamic require avoids bundler errors when the package isn't installed.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const mod = (window as any).Capacitor?.Plugins?.PushNotifications
    return mod ?? null
  } catch {
    return null
  }
}

export async function initPush(): Promise<void> {
  const Push = getPlugin()
  if (!Push) return

  const perm = await Push.requestPermissions()
  if (perm.receive !== 'granted') return

  await Push.register()

  await Push.addListener('registration', async (data: unknown) => {
    const { value: token } = data as { value: string }
    const platform = detectPlatform()
    try {
      await apiPost('/notifications/device-token', { token, platform })
    } catch {
      // non-fatal — in-app notifications still work without push
    }
  })

  await Push.addListener('pushNotificationReceived', (notification: unknown) => {
    window.dispatchEvent(new CustomEvent('push:received', { detail: notification }))
  })

  await Push.addListener('pushNotificationActionPerformed', (action: unknown) => {
    window.dispatchEvent(new CustomEvent('push:tapped', { detail: action }))
  })
}

export async function unregisterPush(token: string): Promise<void> {
  const platform = detectPlatform()
  try {
    await apiFetch('/notifications/device-token', {
      method: 'DELETE',
      body: JSON.stringify({ token, platform }),
    })
  } catch {
    // best-effort
  }
}

function detectPlatform(): 'fcm' | 'apns' {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const platform = (window as any).Capacitor?.getPlatform?.() ?? 'web'
  return platform === 'ios' ? 'apns' : 'fcm'
}
