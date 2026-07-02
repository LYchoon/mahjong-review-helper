import { describe, expect, it } from "vitest";

import { parseTilesString } from "./tiles";

describe("parseTilesString", () => {
  it("expands compact notation", () => {
    expect(parseTilesString("123m 55p")).toEqual(["1m", "2m", "3m", "5p", "5p"]);
  });

  it("keeps red fives", () => {
    expect(parseTilesString("05m")).toEqual(["0m", "5m"]);
  });

  it("normalizes case", () => {
    expect(parseTilesString("12M")).toEqual(["1m", "2m"]);
  });

  it("passes unrecognized chunks through", () => {
    expect(parseTilesString("abc 1m")).toEqual(["abc", "1m"]);
  });

  it("handles empty input", () => {
    expect(parseTilesString("")).toEqual([]);
    expect(parseTilesString("   ")).toEqual([]);
  });
});
