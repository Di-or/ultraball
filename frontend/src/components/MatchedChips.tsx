import type { Matched } from "../lib/types";

interface MatchedChipsProps {
  matched: Matched | null;
}

// Per-result structural provenance (CONTEXT.md: Matched signals) — shared between the
// results grid tile and the card-detail modal, which render it identically.
export function MatchedChips({ matched }: MatchedChipsProps) {
  if (!matched || (matched.tags.length === 0 && !matched.semantic)) return null;

  return (
    <div className="card-matched">
      {matched.tags.map((tag) => (
        <span key={tag} className="matched-tag">
          {tag}
        </span>
      ))}
      {matched.semantic && <span className="matched-tag matched-semantic">meaning</span>}
    </div>
  );
}
