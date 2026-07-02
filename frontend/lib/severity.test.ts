import { describe, expect, it } from "vitest";

import {
  accuracyTextClass,
  dangerBgClass,
  dangerRingClass,
  dangerTextClass,
  shantenLabel,
} from "./severity";

describe("danger bands", () => {
  it("maps band boundaries consistently across class kinds", () => {
    expect(dangerTextClass(0)).toBe("text-best");
    expect(dangerTextClass(15)).toBe("text-best");
    expect(dangerTextClass(16)).toBe("text-good");
    expect(dangerTextClass(35)).toBe("text-good");
    expect(dangerTextClass(36)).toBe("text-inaccuracy");
    expect(dangerTextClass(55)).toBe("text-inaccuracy");
    expect(dangerTextClass(56)).toBe("text-mistake");
    expect(dangerTextClass(80)).toBe("text-mistake");
    expect(dangerTextClass(81)).toBe("text-blunder");
    expect(dangerBgClass(50)).toBe("bg-inaccuracy");
  });

  it("gives certified-safe and very-dangerous tiles a heavier ring", () => {
    expect(dangerRingClass(0)).toBe("ring-2 ring-best");
    expect(dangerRingClass(10)).toBe("ring-1 ring-best");
    expect(dangerRingClass(90)).toBe("ring-2 ring-blunder");
  });
});

describe("accuracyTextClass", () => {
  it("maps accuracy thresholds", () => {
    expect(accuracyTextClass(95)).toBe("text-best");
    expect(accuracyTextClass(80)).toBe("text-good");
    expect(accuracyTextClass(65)).toBe("text-inaccuracy");
    expect(accuracyTextClass(50)).toBe("text-mistake");
    expect(accuracyTextClass(10)).toBe("text-blunder");
  });
});

describe("shantenLabel", () => {
  it("labels win/tenpai/shanten", () => {
    expect(shantenLabel(-1)).toBe("已和");
    expect(shantenLabel(0)).toBe("聽牌");
    expect(shantenLabel(2)).toBe("2 向聽");
  });
});
