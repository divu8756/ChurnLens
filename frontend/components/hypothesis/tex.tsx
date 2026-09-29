import "katex/dist/katex.min.css";

import katex from "katex";

/** Renders LaTeX from the API. KaTeX escapes text and runs without `trust`, so no raw HTML gets through. */
export function Tex({ latex, block = false }: { latex: string; block?: boolean }) {
  const html = katex.renderToString(latex, { displayMode: block, throwOnError: false, trust: false, strict: "ignore" });
  return (
    <span
      className={block ? "block max-w-full overflow-x-auto py-1" : undefined}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
