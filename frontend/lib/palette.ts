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

/** Risk bands keep the same colours in every tab. */
export const RISK_COLOURS: Record<string, string> = {
  High: PALETTE.vermillion,
  Medium: PALETTE.orange,
  Low: PALETTE.blue,
};
