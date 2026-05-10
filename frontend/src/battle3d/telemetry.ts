// TODO: route to the project's analytics sink once chosen.

let firstFrameRecorded = false;

export function recordBattle3DMetric(name: string, value: number): void {
  // eslint-disable-next-line no-console
  console.info(`[battle-3d:telemetry] ${name}`, value);
}

export function markFirstFrame(mountStartMs: number): void {
  if (firstFrameRecorded) return;
  firstFrameRecorded = true;
  recordBattle3DMetric("battle3d.first_frame_ms", performance.now() - mountStartMs);
}

export function _resetTelemetry(): void {
  firstFrameRecorded = false;
}
