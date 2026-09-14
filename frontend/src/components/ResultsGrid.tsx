import type { SearchResult } from "../lib/types";

interface ResultsGridProps {
  results: SearchResult[];
  total: number;
  loading: boolean;
  error: string | null;
}

export function ResultsGrid({ results, total, loading, error }: ResultsGridProps) {
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
          <li key={card.printing_id} className="card-tile">
            <div className="card-name">{card.name}</div>
            <div className="card-meta">
              {card.category}
              {card.stage ? ` · ${card.stage}` : ""}
              {card.hp != null ? ` · ${card.hp} HP` : ""}
            </div>
            {card.types.length > 0 && <div className="card-types">{card.types.join(", ")}</div>}
            {card.matched && (card.matched.tags.length > 0 || card.matched.semantic) && (
              <div className="card-matched">
                {card.matched.tags.map((tag) => (
                  <span key={tag} className="matched-tag">
                    {tag}
                  </span>
                ))}
                {card.matched.semantic && <span className="matched-tag matched-semantic">meaning</span>}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
