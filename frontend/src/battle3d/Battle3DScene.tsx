import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { loadHero } from "./heroLoader";
import { loadDiorama, themeForStage } from "./dioramaLoader";
import { handleEvent, type UnitRig } from "./animationDriver";
import { resolveClip } from "./clipMap";
import { TEMPLATE_TO_3D_ARCHETYPE, DEFAULT_3D_ARCHETYPE } from "./archetypeMap";
import { markFirstFrame, recordBattle3DMetric } from "./telemetry";
import {
  SLOT_POSITIONS_TEAM_A, SLOT_POSITIONS_TEAM_B,
  CAMERA_POSITION, CAMERA_LOOKAT,
  ZOOM_MIN_DIST, ZOOM_MAX_DIST, ZOOM_WHEEL_STEP,
  AMBIENT_INTENSITY, DIRECTIONAL_INTENSITY, DIRECTIONAL_POSITION,
} from "./constants";

export interface InteractiveUnit {
  uid: string;
  name: string;
  template_code?: string;
  faction?: string;
  side?: "A" | "B";
}

export interface Battle3DSceneProps {
  teamA: InteractiveUnit[];
  teamB: InteractiveUnit[];
  stageCode: string | null | undefined;
  pendingActorUid: string | null;
  lastEvent: Record<string, unknown> | null;
  done: boolean;
  templateByUid?: Record<string, string>;
  /** Optional: when the actor is waiting, valid target UIDs that can be clicked. */
  validTargets?: string[];
  /** Optional: invoked with a target UID when the player clicks a valid hero. */
  onAct?: (targetUid: string) => void;
}

function detectWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

function archetypeFor(
  unit: InteractiveUnit,
  templateByUid?: Record<string, string>,
): string {
  const code = unit.template_code ?? templateByUid?.[unit.uid] ?? "";
  return TEMPLATE_TO_3D_ARCHETYPE[code] ?? DEFAULT_3D_ARCHETYPE;
}

export function Battle3DScene(props: Battle3DSceneProps) {
  const [webglOk] = useState<boolean>(() => detectWebGL());
  const containerRef = useRef<HTMLDivElement>(null);
  const rigsRef = useRef<Map<string, UnitRig>>(new Map());
  const lastEventSeenRef = useRef<Record<string, unknown> | null>(null);
  // Mutable mirror of props so the canvas click handler (registered
  // once with deps=[webglOk]) always reads the current valid-targets
  // and onAct without re-attaching listeners on every render.
  const propsRef = useRef(props);
  propsRef.current = props;

  useEffect(() => {
    if (!webglOk || !containerRef.current) return;
    const container = containerRef.current;
    const mountStart = performance.now();
    let firstFrameDone = false;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const threeScene = new THREE.Scene();
    // Fallback background so any gap between the diorama mesh and the
    // camera frustum doesn't show the page's black body color through
    // the alpha:true canvas.
    threeScene.background = new THREE.Color(0x1a1a22);
    const camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / container.clientHeight,
      0.1,
      100,
    );
    camera.position.copy(CAMERA_POSITION);
    camera.lookAt(CAMERA_LOOKAT);

    threeScene.add(new THREE.AmbientLight(0xffffff, AMBIENT_INTENSITY));
    const dir = new THREE.DirectionalLight(0xffffff, DIRECTIONAL_INTENSITY);
    dir.position.copy(DIRECTIONAL_POSITION);
    threeScene.add(dir);

    const mixers: THREE.AnimationMixer[] = [];
    const clock = new THREE.Clock();
    let raf = 0;
    let disposed = false;

    // Diorama backdrop
    loadDiorama(themeForStage(props.stageCode))
      .then(({ scene }) => {
        if (disposed) return;
        threeScene.add(scene);
      })
      .catch(err => console.warn("[battle-3d] diorama load failed", err));

    // Build a side-tagged unit list so we can derive orientation + slot
    // even though CombatUnit shape doesn't carry `side`.
    const sided: { unit: InteractiveUnit; side: "A" | "B"; idx: number }[] = [
      ...props.teamA.map((u, i) => ({ unit: u, side: "A" as const, idx: i })),
      ...props.teamB.map((u, i) => ({ unit: u, side: "B" as const, idx: i })),
    ];

    for (const { unit, side, idx } of sided) {
      const slot =
        side === "A"
          ? SLOT_POSITIONS_TEAM_A[idx % SLOT_POSITIONS_TEAM_A.length]
          : SLOT_POSITIONS_TEAM_B[idx % SLOT_POSITIONS_TEAM_B.length];

      loadHero(archetypeFor(unit, props.templateByUid))
        .then(({ scene, animations, archetype }) => {
          if (disposed) return;
          // scene is already cloned by heroLoader.
          scene.position.set(slot[0], slot[1], slot[2]);
          scene.scale.setScalar(0.55);
          // Stamp uid/side on the root so raycast can identify which
          // unit was clicked by walking up from the intersected mesh.
          scene.userData.uid = unit.uid;
          scene.userData.side = side;
          // Face teammates toward each other across the battle line.
          // Models actually export facing -z (typical glTF "forward"),
          // not +z, so flipping the previous signs here. Team A
          // (negative x) rotates +PI/2 to face +x toward team B;
          // team B mirrors with -PI/2 to face -x toward team A.
          scene.rotation.y = side === "A" ? Math.PI / 2 : -Math.PI / 2;
          threeScene.add(scene);

          const mixer = new THREE.AnimationMixer(scene);
          mixers.push(mixer);
          const availableClips = animations.map(c => c.name);

          const idleName = resolveClip(archetype, "idle", availableClips);
          const idleClip = idleName ? animations.find(c => c.name === idleName) : null;
          if (idleClip) mixer.clipAction(idleClip).play();

          rigsRef.current.set(unit.uid, {
            uid: unit.uid,
            archetype,
            availableClips,
            play: (clipName: string) => {
              const c = animations.find(a => a.name === clipName);
              if (c) {
                const action = mixer.clipAction(c);
                action.reset().setLoop(THREE.LoopOnce, 1).play();
              }
            },
            flashWhite: () => {
              scene.traverse(o => {
                const mesh = o as THREE.Mesh;
                if (!mesh.isMesh) return;
                const mat = mesh.material as
                  | (THREE.Material & {
                      emissive?: THREE.Color;
                      color?: THREE.Color;
                    })
                  | undefined;
                if (!mat) return;
                // Prefer emissive (MeshStandardMaterial / MeshPhongMaterial).
                // Fall back to tinting .color for MeshBasicMaterial (Quaternius
                // druid), which has no emissive channel.
                if (mat.emissive) {
                  const orig = mat.emissive.clone();
                  mat.emissive.setHex(0xffffff);
                  setTimeout(() => mat.emissive!.copy(orig), 200);
                } else if (mat.color) {
                  const orig = mat.color.clone();
                  mat.color.setHex(0xffffff);
                  setTimeout(() => mat.color!.copy(orig), 200);
                }
              });
            },
            floatDamageNumber: (_amount: number) => {
              // DOM overlay — v1.1
            },
            fade: (opacity: number) => {
              scene.traverse(o => {
                const mesh = o as THREE.Mesh;
                if (mesh.isMesh) {
                  const mat = mesh.material as THREE.MeshStandardMaterial;
                  if (!mat) return;
                  mat.transparent = true;
                  mat.opacity = opacity;
                }
              });
            },
          });
        })
        .catch(err =>
          console.warn(`[battle-3d] hero load failed for ${unit.uid}`, err),
        );
    }

    function tick() {
      const dt = clock.getDelta();
      mixers.forEach(m => m.update(dt));
      renderer.render(threeScene, camera);
      if (!firstFrameDone) {
        markFirstFrame(mountStart);
        firstFrameDone = true;
      }
      raf = requestAnimationFrame(tick);
    }
    tick();

    // Raycast: click a hero in the 3D scene to act on it. Reads valid
    // targets + onAct from propsRef so the handler can stay registered
    // across React re-renders without re-binding.
    const raycaster = new THREE.Raycaster();
    const mouseNdc = new THREE.Vector2();
    function pickUidAt(clientX: number, clientY: number): string | null {
      const rect = renderer.domElement.getBoundingClientRect();
      mouseNdc.x = ((clientX - rect.left) / rect.width) * 2 - 1;
      mouseNdc.y = -((clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouseNdc, camera);
      const hits = raycaster.intersectObjects(threeScene.children, true);
      for (const hit of hits) {
        let obj: THREE.Object3D | null = hit.object;
        while (obj && !obj.userData?.uid) obj = obj.parent;
        if (obj && typeof obj.userData.uid === "string") {
          return obj.userData.uid;
        }
      }
      return null;
    }
    function onCanvasClick(e: MouseEvent) {
      const p = propsRef.current;
      if (!p.onAct || !p.validTargets?.length) return;
      const uid = pickUidAt(e.clientX, e.clientY);
      if (uid && p.validTargets.includes(uid)) {
        p.onAct(uid);
      }
    }
    function onCanvasMove(e: MouseEvent) {
      const p = propsRef.current;
      if (!p.onAct || !p.validTargets?.length) {
        renderer.domElement.style.cursor = "default";
        return;
      }
      const uid = pickUidAt(e.clientX, e.clientY);
      renderer.domElement.style.cursor =
        uid && p.validTargets.includes(uid) ? "pointer" : "default";
    }
    renderer.domElement.addEventListener("click", onCanvasClick);
    renderer.domElement.addEventListener("mousemove", onCanvasMove);

    // Wheel zoom: move camera along the lookAt→camera vector, clamp
    // distance to [ZOOM_MIN_DIST, ZOOM_MAX_DIST]. Pinch-zoom on touch
    // devices triggers wheel events too, so this covers both inputs.
    function onCanvasWheel(e: WheelEvent) {
      e.preventDefault();
      const offset = new THREE.Vector3().subVectors(camera.position, CAMERA_LOOKAT);
      const currentDist = offset.length();
      const nextDist = Math.min(
        ZOOM_MAX_DIST,
        Math.max(ZOOM_MIN_DIST, currentDist + e.deltaY * ZOOM_WHEEL_STEP * currentDist),
      );
      offset.setLength(nextDist);
      camera.position.copy(CAMERA_LOOKAT).add(offset);
    }
    renderer.domElement.addEventListener("wheel", onCanvasWheel, { passive: false });

    function onResize() {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    }
    window.addEventListener("resize", onResize);

    return () => {
      recordBattle3DMetric("battle3d.mount_ms", performance.now() - mountStart);
      disposed = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      renderer.domElement.removeEventListener("click", onCanvasClick);
      renderer.domElement.removeEventListener("mousemove", onCanvasMove);
      renderer.domElement.removeEventListener("wheel", onCanvasWheel);
      threeScene.traverse(o => {
        const mesh = o as THREE.Mesh;
        if (mesh.isMesh) {
          mesh.geometry?.dispose();
          const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
          if (Array.isArray(mat)) mat.forEach(x => x.dispose());
          else mat?.dispose();
        }
      });
      renderer.dispose();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
      rigsRef.current.clear();
    };
    // Mount-only: team rosters change via lastEvent/HP, not re-mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [webglOk]);

  // Drive animations from lastEvent
  useEffect(() => {
    if (!props.lastEvent) return;
    if (props.lastEvent === lastEventSeenRef.current) return;
    lastEventSeenRef.current = props.lastEvent;
    handleEvent(props.lastEvent as never, rigsRef.current);
  }, [props.lastEvent]);

  if (!webglOk) {
    return <div className="battle-watermark">BATTLE</div>;
  }
  return (
    <div
      ref={containerRef}
      className="battle-3d-canvas"
      data-testid="battle-3d-canvas"
      style={{ position: "absolute", inset: 0 }}
    />
  );
}
