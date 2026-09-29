// Risk Predictions helpers. Reasons arrive as text like "Contract: Month-to-month (+0.74)";
// the chip shows the text and colours it by the sign the server already wrote.
export type Reason = { text: string; contribution: string; raises: boolean };

const REASON = /^(.*) \(([+-]\d+(?:\.\d+)?)\)$/;

export function parseReason(reason: string): Reason {
  const match = REASON.exec(reason);
  if (!match) return { text: reason, contribution: "", raises: true };
  return { text: match[1], contribution: match[2], raises: match[2].startsWith("+") };
}

export const SEARCH_DEBOUNCE_MS = 300;
