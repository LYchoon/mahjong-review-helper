/** Tile-notation helpers shared across components. */

export const HONOR_LABEL: Record<string, string> = {
  "1z": "東",
  "2z": "南",
  "3z": "西",
  "4z": "北",
  "5z": "白",
  "6z": "發",
  "7z": "中",
};

export const SUIT_LABEL: Record<string, string> = {
  m: "萬",
  p: "筒",
  s: "索",
};

/**
 * Expand compact notation into individual tiles:
 *   "123m 55p 0s" → ["1m", "2m", "3m", "5p", "5p", "0s"]
 * Unrecognized chunks pass through unchanged (the backend validates).
 */
export function parseTilesString(s: string): string[] {
  const out: string[] = [];
  for (const chunk of s.trim().split(/\s+/).filter(Boolean)) {
    const m = chunk.match(/^([0-9]+)([mpsz])$/i);
    if (m) {
      for (const d of m[1]) out.push(`${d}${m[2].toLowerCase()}`);
    } else {
      out.push(chunk);
    }
  }
  return out;
}
