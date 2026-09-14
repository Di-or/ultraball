interface ConceptIndicatorProps {
  query: string;
  onRemove: () => void;
}

// The removable pill for the semantic/tag part of a query (CONTEXT.md: Concept indicator).
// Shows the player's own words — never the internal `concept_rewritten` string, which stays
// server-side (CONTEXT.md: Normalized mechanical description).
export function ConceptIndicator({ query, onRemove }: ConceptIndicatorProps) {
  return (
    <div className="concept-indicator" role="status">
      <span className="concept-indicator-label">Concept:</span>
      <span className="concept-indicator-text">{query}</span>
      <button type="button" aria-label="Remove concept" onClick={onRemove}>
        ×
      </button>
    </div>
  );
}
