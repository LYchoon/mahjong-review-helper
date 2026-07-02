import { describe, expect, it } from "vitest";

import { detectLogFormat } from "./api";

describe("detectLogFormat", () => {
  it("detects tenhou logs by the log array", () => {
    expect(detectLogFormat({ title: [], log: [[[0, 0, 0]]] })).toBe("tenhou");
  });

  it("detects majsoul records under data/record/actions", () => {
    const action = { name: ".lq.RecordNewRound", data: {} };
    expect(detectLogFormat({ head: {}, data: [action] })).toBe("majsoul");
    expect(detectLogFormat({ record: [action] })).toBe("majsoul");
    expect(detectLogFormat({ actions: [action] })).toBe("majsoul");
  });

  it("detects a bare majsoul action array", () => {
    expect(detectLogFormat([{ name: "RecordDealTile", data: {} }])).toBe("majsoul");
  });

  it("returns null for unknown shapes", () => {
    expect(detectLogFormat({})).toBeNull();
    expect(detectLogFormat(null)).toBeNull();
    expect(detectLogFormat("string")).toBeNull();
    expect(detectLogFormat({ data: [{ foo: 1 }] })).toBeNull();
  });
});
