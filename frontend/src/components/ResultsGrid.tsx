import { MatchedChips } from "./MatchedChips";
import type { SearchResult } from "../lib/types";

interface ResultsGridProps {
  results: SearchResult[];
  total: number;
  loading: boolean;
  error: string | null;
  onSelectCard: (card: SearchResult) => void;
}

export function ResultsGrid({ results, total, loading, error, onSelectCard }: ResultsGridProps) {
  if (error) {
    return <p role="alert">{error}</p>;
  }

  if (loading) {
    return <p aria-live="polite">Searching…</p>;
  }

  if (results.length === 0) {
    return <p>No cards match.</p>;
  }

  return (
    <div>
      <p className="results-count">{total} cards</p>
      <ul className="results-grid" aria-label="Search results">
        {results.map((card) => (
          <li key={card.printing_id}>
            <button type="button" className="card-tile" onClick={() => onSelectCard(card)}>
              <div className="card-name">{card.name}</div>
              <div className="card-meta">
                {card.category}
                {card.stage ? ` · ${card.stage}` : ""}
                {card.hp != null ? ` · ${card.hp} HP` : ""}
              </div>
              {card.types.length > 0 && <div className="card-types">{card.types.join(", ")}</div>}
              <MatchedChips matched={card.matched} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
