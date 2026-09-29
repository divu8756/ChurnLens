// Okabe-Ito colours: distinguishable with the common kinds of colour blindness.
export const PALETTE = {
  orange: "#E69F00",
  skyBlue: "#56B4E9",
  green: "#009E73",
  yellow: "#F0E442",
  blue: "#0072B2",
  vermillion: "#D55E00",
  purple: "#CC79A7",
  grey: "#999999",
} as const;

export const SERIES = [PALETTE.blue, PALETTE.orange, PALETTE.green, PALETTE.vermillion, PALETTE.skyBlue, PALETTE.purple];

/** Blue (low, 0) to vermillion (high, 1): a colour-blind-safe two-colour ramp. */
export function toneColour(tone: number): string {
  const t = Math.min(1, Math.max(0, tone));
  const from = [0x00, 0x72, 0xb2];
  const to = [0xd5, 0x5e, 0x00];
  const mix = from.map((c, i) => Math.round(c + (to[i] - c) * t));
  return `rgb(${mix.join(", ")})`;
}

/** Risk bands keep the same colours in every tab. */
export const RISK_COLOURS: Record<string, string> = {
  High: PALETTE.vermillion,
  Medium: PALETTE.orange,
  Low: PALETTE.blue,
};
