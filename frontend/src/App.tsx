import { useEffect, useReducer, useState } from "react";
import { CardDetailModal } from "./components/CardDetailModal";
import { ConceptIndicator } from "./components/ConceptIndicator";
import { DeckPanel } from "./components/DeckPanel";
import { FilterPanel } from "./components/FilterPanel";
import { Pagination } from "./components/Pagination";
import { ResultsGrid } from "./components/ResultsGrid";
import { SearchBox } from "./components/SearchBox";
import { search } from "./lib/api";
import type { Category, SearchResponse, SearchResult } from "./lib/types";
import { deckStateReducer, initialDeckState } from "./state/deckState";
import { initialSearchState, searchStateReducer } from "./state/searchState";

export function App() {
  const [state, dispatch] = useReducer(searchStateReducer, initialSearchState);
  const [deckState, deckDispatch] = useReducer(deckStateReducer, initialDeckState);
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

  function handleAddToDeck(card: SearchResult) {
    deckDispatch({
      type: "card-added",
      card: {
        printing_id: card.printing_id,
        name: card.name,
        // The backend serves `category` as a plain string (app/search/models.py); the
        // search gate already constrains it to one of the three deck categories.
        category: card.category as Category,
        set_code: card.set_code,
        local_id: card.local_id,
        energy_type: null,
      },
    });
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
            onAddToDeck={handleAddToDeck}
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
        <DeckPanel lines={deckState.lines} dispatch={deckDispatch} />
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
