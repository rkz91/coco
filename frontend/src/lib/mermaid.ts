/**
 * Mermaid detection and text segmentation utility.
 *
 * Parses text containing fenced mermaid code blocks and returns
 * typed segments for mixed rendering (text + diagrams).
 */

export type Segment =
  | { type: 'text'; content: string }
  | { type: 'mermaid'; code: string }
  | { type: 'code'; lang: string; code: string };

const FENCED_BLOCK_RE = /```(\w*)\n([\s\S]*?)```/g;

/** Quick check — avoids full parsing when no mermaid blocks exist. */
export function hasMermaidBlocks(text: string): boolean {
  return /```mermaid\n[\s\S]*?```/.test(text);
}

/**
 * Split text into segments of plain text, mermaid diagrams, and code blocks.
 * Only complete fenced blocks are extracted — partial fences (e.g. during
 * SSE streaming) remain as plain text.
 */
export function parseMermaidSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(FENCED_BLOCK_RE)) {
    const matchStart = match.index!;
    // Push any text before this fenced block
    if (matchStart > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, matchStart) });
    }

    const lang = (match[1] ?? '').toLowerCase();
    const code = match[2]?.trim() ?? '';

    if (lang === 'mermaid') {
      segments.push({ type: 'mermaid', code });
    } else {
      segments.push({ type: 'code', lang, code });
    }

    lastIndex = matchStart + match[0].length;
  }

  // Remaining text after last block
  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) });
  }

  return segments;
}
