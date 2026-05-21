import { describe, it, expect, vi } from "vitest";
import { handleEvent, UnitRig } from "../animationDriver";

function makeRig(uid: string, archetype: string): UnitRig {
  return {
    uid,
    archetype,
    availableClips: ["Idle_Weapon", "Sword_Attack", "RecieveHit", "Death"],
    play: vi.fn(),
    flashWhite: vi.fn(),
    floatDamageNumber: vi.fn(),
    fade: vi.fn(),
  };
}

describe("animationDriver.handleEvent", () => {
  it("DAMAGE: attacker plays attack, defender plays hit + flashes + floats damage", () => {
    const attacker = makeRig("a1", "knight");
    const defender = makeRig("b1", "knight");
    const rigs = new Map([["a1", attacker], ["b1", defender]]);

    handleEvent(
      { type: "DAMAGE", actor_uid: "a1", target_uid: "b1", amount: 42 },
      rigs,
    );

    expect(attacker.play).toHaveBeenCalledWith("Sword_Attack");
    expect(defender.play).toHaveBeenCalledWith("RecieveHit");
    expect(defender.flashWhite).toHaveBeenCalled();
    expect(defender.floatDamageNumber).toHaveBeenCalledWith(42, { crit: false });
  });

  it("DEATH: victim plays die clip and fades to 0.4", () => {
    const victim = makeRig("b1", "knight");
    const rigs = new Map([["b1", victim]]);

    handleEvent({ type: "DEATH", target_uid: "b1" }, rigs);

    expect(victim.play).toHaveBeenCalledWith("Death");
    expect(victim.fade).toHaveBeenCalledWith(0.4);
  });

  it("SPECIAL: attacker plays attack clip and flashes", () => {
    const attacker = makeRig("a1", "knight");
    handleEvent({ type: "SPECIAL", actor_uid: "a1" }, new Map([["a1", attacker]]));
    expect(attacker.play).toHaveBeenCalledWith("Sword_Attack");
    expect(attacker.flashWhite).toHaveBeenCalled();
  });

  it("LIMIT_BREAK: attacker plays attack clip and flashes", () => {
    const attacker = makeRig("a1", "knight");
    handleEvent({ type: "LIMIT_BREAK", unit: "a1" }, new Map([["a1", attacker]]));
    expect(attacker.play).toHaveBeenCalledWith("Sword_Attack");
    expect(attacker.flashWhite).toHaveBeenCalled();
  });

  it("DEFEND_ABSORB: defender floats a defend popup", () => {
    const defender = makeRig("b1", "knight");
    handleEvent({ type: "DEFEND_ABSORB", unit: "b1", amount: 18 }, new Map([["b1", defender]]));
    expect(defender.floatDamageNumber).toHaveBeenCalledWith(18, { kind: "defend" });
  });

  it("unknown event type is a no-op", () => {
    const r = makeRig("a1", "knight");
    handleEvent({ type: "TURN_START", actor_uid: "a1" }, new Map([["a1", r]]));
    expect(r.play).not.toHaveBeenCalled();
  });

  it("missing rig is a no-op", () => {
    handleEvent({ type: "DAMAGE", actor_uid: "ghost", target_uid: "x" }, new Map());
    // no throw
  });
});
