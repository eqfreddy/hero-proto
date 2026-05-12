// Battle 3D telemetry. Mirrors metrics to the console for quick
// dev eyeballing AND posts to /telemetry/event, which forwards to
// the PostHog analytics wrapper (silent no-op when PostHog isn't
// configured). Uses fetch + keepalive so the call survives lazy
// unmounts of Battle3DScene without blocking the UI thread.

import { useAuthStore } from "../store/auth";

let firstFrameRecorded = false;

function postEvent(name: string, value?: number): void {
  const jwt = useAuthStore.getState().jwt;
  if (!jwt) return; // unauth → backend would 401; skip silently.
  try {
    void fetch("/telemetry/event", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwt}`,
      },
      body: JSON.stringify({ name, value }),
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    // Telemetry must never break the page.
  }
}

export function recordBattle3DMetric(name: string, value: number): void {
  // eslint-disable-next-line no-console
  console.info(`[battle-3d:telemetry] ${name}`, value);
  postEvent(name, value);
}

export function markFirstFrame(mountStartMs: number): void {
  if (firstFrameRecorded) return;
  firstFrameRecorded = true;
  recordBattle3DMetric("battle3d.first_frame_ms", performance.now() - mountStartMs);
}

export function _resetTelemetry(): void {
  firstFrameRecorded = false;
}
