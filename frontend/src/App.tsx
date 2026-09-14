import { useEffect, useReducer, useState } from "react";
import { CardDetailModal } from "./components/CardDetailModal";
import { ConceptIndicator } from "./components/ConceptIndicator";
import { FilterPanel } from "./components/FilterPanel";
import { Pagination } from "./components/Pagination";
import { ResultsGrid } from "./components/ResultsGrid";
import { SearchBox } from "./components/SearchBox";
import { search } from "./lib/api";
import type { SearchResponse, SearchResult } from "./lib/types";
import { initialSearchState, searchStateReducer } from "./state/searchState";

export function App() {
  const [state, dispatch] = useReducer(searchStateReducer, initialSearchState);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCard, setSelectedCard] = useState<SearchResult | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    search(
      {
        // `query` is only ever non-null the one tick right after an NL submit — the
        // reducer clears it once resolved, so a later filter/facet edit never re-parses.
        query: state.query,
        filters: state.filters,
        facets: state.facets,
        limit: state.limit,
        offset: state.offset,
      },
      controller.signal
    )
      .then((result) => {
        setResponse(result);
        // The parse ticked these filters on — surface them in the panel (CONTEXT.md: Filter
        // panel). Reconciling this into state deliberately doesn't bump `fetchRevision`
        // (see its doc comment), so this never causes a second, ranking-downgrading fetch.
        if (state.query) {
          dispatch({ type: "query-resolved", filters: result.filters });
        }
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "search failed");
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.fetchRevision]);

  function handleNlSubmit(query: string) {
    dispatch({ type: "query-submitted", query });
  }

  return (
    <div className="app-shell">
      <header>
        <h1>Ultraball</h1>
        <SearchBox onSubmit={handleNlSubmit} disabled={loading} />
        {state.conceptActive && (
          <ConceptIndicator
            query={state.lastQuery}
            onRemove={() => dispatch({ type: "concept-removed" })}
          />
        )}
      </header>
      <main className="split-view">
        <FilterPanel
          filters={state.filters}
          facets={state.facets}
          onFilterChange={(patch) => dispatch({ type: "filter-changed", patch })}
          onFacetChange={(patch) => dispatch({ type: "facet-changed", patch })}
        />
        <section className="results-pane">
          <ResultsGrid
            results={response?.results ?? []}
            total={response?.total ?? 0}
            loading={loading}
            error={error}
            onSelectCard={setSelectedCard}
          />
          {response && (
            <Pagination
              offset={state.offset}
              limit={state.limit}
              total={response.total}
              onPageChange={(offset) => dispatch({ type: "page-changed", offset })}
            />
          )}
        </section>
        <aside className="deck-panel" aria-label="Deck">
          <h2>Deck</h2>
          <p>Deck building lands in a follow-up ticket.</p>
        </aside>
      </main>
      {selectedCard && (
        <CardDetailModal
          entityId={selectedCard.entity_id}
          matched={selectedCard.matched}
          onClose={() => setSelectedCard(null)}
        />
      )}
    </div>
  );
}
