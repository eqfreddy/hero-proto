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
  hp?: number;
  max_hp?: number;
  dead?: boolean;
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

    // World-space HP bars: HTML overlay sibling to the canvas, one bar
    // per hero. Each frame we project the hero's head position to CSS
    // pixels and update the bar's transform + fill from latest props.
    const barsRoot = document.createElement("div");
    barsRoot.style.cssText = "position:absolute;inset:0;pointer-events:none;overflow:hidden;";
    container.appendChild(barsRoot);

    // Floating damage number animation. Injected once per scene mount.
    // ID-gated so re-mounts during HMR don't duplicate the rule.
    if (typeof document !== "undefined" && !document.getElementById("lb3-fx-keyframes")) {
      const styleEl = document.createElement("style");
      styleEl.id = "lb3-fx-keyframes";
      styleEl.textContent =
        "@keyframes lb3-float{" +
        "0%{opacity:0;transform:translateY(0) scale(0.9)}" +
        "12%{opacity:1;transform:translateY(-6px) scale(1.05)}" +
        "100%{opacity:0;transform:translateY(-44px) scale(1)}" +
        "}" +
        "@keyframes lb3-shake{0%,100%{transform:translate(0,0)}25%{transform:translate(-4px,2px)}" +
        "50%{transform:translate(3px,-2px)}75%{transform:translate(-2px,3px)}}";
      document.head.appendChild(styleEl);
    }
    const bars = new Map<string, { el: HTMLDivElement; fill: HTMLDivElement; anchor: THREE.Object3D }>();
    // Aura discs — glowing ring under each hero's feet. Team-colored so
    // ally vs enemy is readable at a glance. Pulsed in the tick loop.
    // Stacked discs per unit: a bright inner core + a wider outer ring.
    // Each layer pulses on its own offset so the aura "breathes" rather
    // than just scaling uniformly. Additive blending so it reads as light.
    interface AuraLayer { mesh: THREE.Mesh; mat: THREE.MeshBasicMaterial; baseOpacity: number; pulseScale: number; phase: number }
    const auras = new Map<string, AuraLayer[]>();
    const auraGeomOuter = new THREE.RingGeometry(0.85, 1.45, 48);
    const auraGeomInner = new THREE.RingGeometry(0.30, 0.85, 48);
    const auraGeomCore  = new THREE.CircleGeometry(0.65, 48);
    auraGeomOuter.rotateX(-Math.PI / 2);
    auraGeomInner.rotateX(-Math.PI / 2);
    auraGeomCore.rotateX(-Math.PI / 2);
    function makeAura(uid: string, side: "A" | "B", anchor: THREE.Object3D) {
      // Cyan for allies, magenta for enemies — matches faction palette tokens.
      const color = side === "A" ? 0x00ffe0 : 0xff2d78;
      const layers: AuraLayer[] = [];
      // Outer wide ring — slow, low opacity, big scale swing.
      const outerMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.65, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
      const outer = new THREE.Mesh(auraGeomOuter, outerMat);
      outer.position.copy(anchor.position); outer.position.y = 0.02;
      threeScene.add(outer);
      layers.push({ mesh: outer, mat: outerMat, baseOpacity: 0.65, pulseScale: 0.25, phase: Math.random() * Math.PI * 2 });
      // Inner ring — brighter, faster pulse.
      const innerMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
      const inner = new THREE.Mesh(auraGeomInner, innerMat);
      inner.position.copy(anchor.position); inner.position.y = 0.03;
      threeScene.add(inner);
      layers.push({ mesh: inner, mat: innerMat, baseOpacity: 0.85, pulseScale: 0.18, phase: Math.random() * Math.PI * 2 });
      // Soft glow core under the feet — fixed scale, gentle opacity pulse.
      const coreMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
      const core = new THREE.Mesh(auraGeomCore, coreMat);
      core.position.copy(anchor.position); core.position.y = 0.015;
      threeScene.add(core);
      layers.push({ mesh: core, mat: coreMat, baseOpacity: 0.55, pulseScale: 0, phase: Math.random() * Math.PI * 2 });
      auras.set(uid, layers);
    }
    function updateAuras(t: number) {
      for (const layers of auras.values()) {
        for (const l of layers) {
          const k = 0.5 + 0.5 * Math.sin(t * 2.2 + l.phase);
          const s = 1 + l.pulseScale * (k - 0.5) * 2; // 1 ± pulseScale
          l.mesh.scale.set(s, s, s);
          l.mat.opacity = l.baseOpacity * (0.7 + 0.3 * k);
        }
      }
    }
    const HEAD_OFFSET = new THREE.Vector3(0, 2.6, 0);
    const tmpProj = new THREE.Vector3();

    function makeBar(uid: string): { el: HTMLDivElement; fill: HTMLDivElement } {
      const el = document.createElement("div");
      el.style.cssText = "position:absolute;left:0;top:0;width:64px;height:6px;margin:-3px 0 0 -32px;background:rgba(0,0,0,0.65);border:1px solid rgba(0,0,0,0.85);border-radius:3px;overflow:hidden;will-change:transform;display:none;";
      const fill = document.createElement("div");
      fill.style.cssText = "height:100%;background:#4caf50;transition:width 0.25s, background 0.25s;";
      el.appendChild(fill);
      barsRoot.appendChild(el);
      bars.set(uid, { el, fill, anchor: new THREE.Object3D() }); // anchor replaced after load
      return { el, fill };
    }

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
          // Reserve an HP bar element + remember the scene as its anchor.
          makeBar(unit.uid);
          bars.get(unit.uid)!.anchor = scene;
          // Face teammates toward each other across the battle line.
          // Models actually export facing -z (typical glTF "forward"),
          // not +z, so flipping the previous signs here. Team A
          // (negative x) rotates +PI/2 to face +x toward team B;
          // team B mirrors with -PI/2 to face -x toward team A.
          scene.rotation.y = side === "A" ? Math.PI / 2 : -Math.PI / 2;
          threeScene.add(scene);
          makeAura(unit.uid, side, scene);

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
            floatDamageNumber: (amount: number, opts?: { crit?: boolean; kind?: 'damage' | 'heal' | 'defend' }) => {
              const anchor = bars.get(unit.uid)?.anchor;
              if (!anchor) return;
              const cw = container.clientWidth;
              const ch = container.clientHeight;
              tmpProj.copy(anchor.position).add(HEAD_OFFSET).project(camera);
              if (tmpProj.z > 1) return;
              const px = (tmpProj.x * 0.5 + 0.5) * cw;
              const py = (-tmpProj.y * 0.5 + 0.5) * ch - 14;
              const el = document.createElement('div');
              const kind = opts?.kind ?? 'damage';
              const crit = !!opts?.crit;
              const color =
                kind === 'heal'   ? '#5ad8a3' :
                kind === 'defend' ? '#a8c4ff' :
                crit              ? '#ffd86b' :
                                    '#ffffff';
              const size = crit ? 28 : 20;
              const label =
                kind === 'defend' ? 'DEFEND'
                : kind === 'heal' ? `+${amount}`
                : crit            ? `${amount}!`
                :                   String(amount);
              el.textContent = label;
              // Outer wraps positioning so we can animate transform on the inner
              // element without fighting the per-event x/y placement.
              const wrap = document.createElement('div');
              wrap.style.cssText = `position:absolute;left:${px}px;top:${py}px;transform:translate(-50%,-100%);pointer-events:none;`;
              el.style.cssText = [
                'font-family:Space Grotesk, system-ui, sans-serif',
                'font-weight:800',
                `font-size:${size}px`,
                `color:${color}`,
                'text-shadow:0 2px 6px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,0.9)',
                'letter-spacing:0.04em',
                'will-change:transform,opacity',
                `animation:lb3-float ${crit ? 1400 : 1100}ms ease-out forwards`,
              ].join(';');
              wrap.appendChild(el);
              barsRoot.appendChild(wrap);
              setTimeout(() => { el.remove(); }, crit ? 1450 : 1150);
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

    function updateBars() {
      if (bars.size === 0) return;
      const p = propsRef.current;
      const units = [...p.teamA, ...p.teamB];
      const byUid = new Map(units.map(u => [u.uid, u]));
      const cw = container.clientWidth;
      const ch = container.clientHeight;
      for (const [uid, b] of bars) {
        const u = byUid.get(uid);
        if (!u || !b.anchor) { b.el.style.display = "none"; continue; }
        if (u.dead) { b.el.style.display = "none"; continue; }
        tmpProj.copy(b.anchor.position).add(HEAD_OFFSET).project(camera);
        // Skip if behind camera (z > 1) or off-screen.
        if (tmpProj.z > 1) { b.el.style.display = "none"; continue; }
        const px = (tmpProj.x * 0.5 + 0.5) * cw;
        const py = (-tmpProj.y * 0.5 + 0.5) * ch;
        b.el.style.display = "block";
        b.el.style.transform = `translate(${px}px, ${py}px)`;
        if (u.max_hp != null && u.max_hp > 0 && u.hp != null) {
          const pct = Math.max(0, Math.min(1, u.hp / u.max_hp));
          b.fill.style.width = `${pct * 100}%`;
          b.fill.style.background = pct > 0.5 ? "#4caf50" : pct > 0.25 ? "#e8a35a" : "#e85a78";
        }
      }
    }

    function tick() {
      const dt = clock.getDelta();
      mixers.forEach(m => m.update(dt));
      updateAuras(clock.elapsedTime);
      renderer.render(threeScene, camera);
      updateBars();
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
      if (barsRoot.parentNode === container) {
        container.removeChild(barsRoot);
      }
      bars.clear();
      auras.clear();
      auraGeomOuter.dispose();
      auraGeomInner.dispose();
      auraGeomCore.dispose();
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
