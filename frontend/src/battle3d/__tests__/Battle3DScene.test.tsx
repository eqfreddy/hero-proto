import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Battle3DScene } from "../Battle3DScene";

beforeEach(() => {
  // Force WebGL detection to fail.
  HTMLCanvasElement.prototype.getContext = vi.fn(() => null);
});

const stubProps = {
  teamA: [],
  teamB: [],
  stageCode: "tutorial_first_ticket",
  pendingActorUid: null,
  lastEvent: null,
  done: false,
};

describe("Battle3DScene", () => {
  it("renders watermark fallback when WebGL is unavailable", () => {
    render(<Battle3DScene {...stubProps} />);
    expect(screen.getByText(/BATTLE/i)).toBeInTheDocument();
  });
});
