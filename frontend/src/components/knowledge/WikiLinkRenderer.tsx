import React, { useMemo } from 'react';
import { cn } from '../../lib/utils';
import { EntityHoverCard } from './EntityHoverCard';

// ── Types ──────────────────────────────────────────────────────────────

interface KnownEntity {
  gid: string;
  name: string;
  type: string;
}

interface WikiLinkRendererProps {
  content: string;
  knownEntities: KnownEntity[];
  onEntityClick: (gid: string) => void;
}

// ── URL / email detection pattern ──────────────────────────────────────

const URL_EMAIL_RE = /(?:https?:\/\/\S+|[\w.-]+@[\w.-]+\.\w+)/gi;

// ── Helpers ────────────────────────────────────────────────────────────

/**
 * Build a sorted array of entities suitable for matching:
 *  - Filter out names shorter than 3 characters
 *  - Sort by name length descending (longest first) to avoid partial matches
 */
function prepareEntities(entities: KnownEntity[]): KnownEntity[] {
  return entities
    .filter((e) => e.name.length >= 3)
    .sort((a, b) => b.name.length - a.name.length);
}

/**
 * Escape special regex characters in a string.
 */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Build a single regex that matches any entity name (case-insensitive,
 * word-boundary-aware). Entity names are sorted longest-first so the
 * alternation picks the longest match.
 */
function buildEntityRegex(entities: KnownEntity[]): RegExp | null {
  if (entities.length === 0) return null;
  const alternatives = entities.map((e) => escapeRegex(e.name));
  // Use word boundaries so "Risk" doesn't match inside "Risky"
  return new RegExp(`\\b(${alternatives.join('|')})\\b`, 'gi');
}

/**
 * Identify character ranges in `text` that are inside URLs or emails
 * so we can skip matches there.
 */
function getProtectedRanges(text: string): Array<[number, number]> {
  const ranges: Array<[number, number]> = [];
  let m: RegExpExecArray | null;
  const re = new RegExp(URL_EMAIL_RE.source, URL_EMAIL_RE.flags);
  while ((m = re.exec(text)) !== null) {
    ranges.push([m.index, m.index + m[0].length]);
  }
  return ranges;
}

function isInsideProtectedRange(
  idx: number,
  len: number,
  ranges: Array<[number, number]>,
): boolean {
  const end = idx + len;
  return ranges.some(([start, stop]) => idx >= start && end <= stop);
}

// ── Segment type ───────────────────────────────────────────────────────

interface TextSegment {
  type: 'text';
  value: string;
}

interface LinkSegment {
  type: 'link';
  value: string; // original cased text
  entity: KnownEntity;
}

type Segment = TextSegment | LinkSegment;

/**
 * Split content into an array of plain-text and wikilink segments.
 */
function segmentContent(
  content: string,
  sortedEntities: KnownEntity[],
): Segment[] {
  const regex = buildEntityRegex(sortedEntities);
  if (!regex) return [{ type: 'text', value: content }];

  const protectedRanges = getProtectedRanges(content);
  const entityMap = new Map<string, KnownEntity>();
  for (const e of sortedEntities) {
    entityMap.set(e.name.toLowerCase(), e);
  }

  const segments: Segment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  // Reset regex state
  regex.lastIndex = 0;

  while ((match = regex.exec(content)) !== null) {
    const matchText = match[0];
    const matchStart = match.index;

    // Skip if inside a URL or email
    if (isInsideProtectedRange(matchStart, matchText.length, protectedRanges)) {
      continue;
    }

    const entity = entityMap.get(matchText.toLowerCase());
    if (!entity) continue;

    // Push any preceding plain text
    if (matchStart > lastIndex) {
      segments.push({ type: 'text', value: content.slice(lastIndex, matchStart) });
    }

    segments.push({ type: 'link', value: matchText, entity });
    lastIndex = matchStart + matchText.length;
  }

  // Remaining tail
  if (lastIndex < content.length) {
    segments.push({ type: 'text', value: content.slice(lastIndex) });
  }

  return segments;
}

// ── WikiLink span ──────────────────────────────────────────────────────

function WikiLinkSpan({
  entity,
  displayText,
  onEntityClick,
}: {
  entity: KnownEntity;
  displayText: string;
  onEntityClick: (gid: string) => void;
}) {
  return (
    <EntityHoverCard
      entityGid={entity.gid}
      entityName={entity.name}
      entityType={entity.type}
      onEntityClick={onEntityClick}
    >
      <button
        type="button"
        onClick={() => onEntityClick(entity.gid)}
        className={cn(
          'inline text-left',
          'text-accent underline decoration-accent/30 decoration-1 underline-offset-2',
          'hover:decoration-accent/60 hover:text-accent/90',
          'transition-colors cursor-pointer',
          'rounded-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent/50',
        )}
      >
        {displayText}
      </button>
    </EntityHoverCard>
  );
}

// ── Main component ─────────────────────────────────────────────────────

export const WikiLinkRenderer = React.memo(function WikiLinkRenderer({
  content,
  knownEntities,
  onEntityClick,
}: WikiLinkRendererProps) {
  const sortedEntities = useMemo(
    () => prepareEntities(knownEntities),
    [knownEntities],
  );

  const segments = useMemo(
    () => segmentContent(content, sortedEntities),
    [content, sortedEntities],
  );

  // If no links found, render as plain text (fast path)
  if (segments.length === 1 && segments[0].type === 'text') {
    return (
      <div className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
        {content}
      </div>
    );
  }

  return (
    <div className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
      {segments.map((seg, i) =>
        seg.type === 'text' ? (
          <React.Fragment key={i}>{seg.value}</React.Fragment>
        ) : (
          <WikiLinkSpan
            key={`${seg.entity.gid}-${i}`}
            entity={seg.entity}
            displayText={seg.value}
            onEntityClick={onEntityClick}
          />
        ),
      )}
    </div>
  );
});
