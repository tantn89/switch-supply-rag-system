// Parse inline [source_id] citations out of an assistant message and
// return text segments interleaved with citation tokens for rendering.
import type { Citation } from "./types";

export type Segment =
  | { kind: "text"; text: string }
  | { kind: "citation"; sourceId: string; citation?: Citation };

const CITATION_RE = /\[([a-z_]+:[^\]]+)\]/gi;

export function parseCitations(
  text: string,
  citations: Citation[] = [],
): Segment[] {
  const byId = new Map(citations.map((c) => [c.source_id, c]));
  const segments: Segment[] = [];
  let lastIdx = 0;
  for (const match of text.matchAll(CITATION_RE)) {
    const start = match.index ?? 0;
    if (start > lastIdx) {
      segments.push({ kind: "text", text: text.slice(lastIdx, start) });
    }
    const sourceId = match[1];
    segments.push({
      kind: "citation",
      sourceId,
      citation: byId.get(sourceId),
    });
    lastIdx = start + match[0].length;
  }
  if (lastIdx < text.length) {
    segments.push({ kind: "text", text: text.slice(lastIdx) });
  }
  return segments;
}
