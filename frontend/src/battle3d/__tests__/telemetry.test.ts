import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  recordBattle3DMetric,
  markFirstFrame,
  _resetTelemetry,
} from "../telemetry";

describe("battle3d telemetry", () => {
  let infoSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    _resetTelemetry();
    infoSpy = vi.spyOn(console, "info").mockImplementation(() => {});
  });

  afterEach(() => {
    infoSpy.mockRestore();
  });

  it("recordBattle3DMetric logs name and value", () => {
    recordBattle3DMetric("battle3d.test_metric", 42);
    expect(infoSpy).toHaveBeenCalledWith(
      "[battle-3d:telemetry] battle3d.test_metric",
      42,
    );
  });

  it("markFirstFrame records elapsed only once", () => {
    const start = performance.now() - 10;
    markFirstFrame(start);
    markFirstFrame(start);
    expect(infoSpy).toHaveBeenCalledTimes(1);
    const [label, value] = infoSpy.mock.calls[0];
    expect(label).toBe("[battle-3d:telemetry] battle3d.first_frame_ms");
    expect(typeof value).toBe("number");
    expect(value as number).toBeGreaterThanOrEqual(0);
  });

  it("_resetTelemetry allows markFirstFrame to fire again", () => {
    markFirstFrame(performance.now());
    _resetTelemetry();
    markFirstFrame(performance.now());
    expect(infoSpy).toHaveBeenCalledTimes(2);
  });
});
