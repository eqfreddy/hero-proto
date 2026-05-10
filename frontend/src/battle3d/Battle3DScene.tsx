import { useEffect, useRef, useState } from "react";

export interface InteractiveUnit {
  uid: string;
  name: string;
  template_code?: string;
  faction?: string;
  side: "A" | "B";
  hp: number;
  hp_max: number;
}

export interface Battle3DSceneProps {
  teamA: InteractiveUnit[];
  teamB: InteractiveUnit[];
  stageCode: string | null | undefined;
  pendingActorUid: string | null;
  lastEvent: Record<string, unknown> | null;
  done: boolean;
}

function detectWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export function Battle3DScene(_props: Battle3DSceneProps) {
  const [webglOk] = useState<boolean>(() => detectWebGL());
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!webglOk) return;
    // Three.js setup lands in Task 6.
  }, [webglOk]);

  if (!webglOk) {
    return <div className="battle-watermark">BATTLE</div>;
  }
  return <div ref={containerRef} className="battle-3d-canvas" data-testid="battle-3d-canvas" />;
}
