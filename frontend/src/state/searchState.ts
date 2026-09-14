import { EMPTY_FACETS, EMPTY_FILTERS, type Facets, type Filters } from "../lib/types";

export interface SearchState {
  /** Set only right after an NL submit; the effect sends it once, then clears it on
   * resolution so a later filter/facet edit never re-triggers a parse. */
  query: string | null;
  /** The last submitted NL text, kept only for display in the search box / concept indicator. */
  lastQuery: string;
  /** Whether the concept indicator (CONTEXT.md: Concept indicator) is showing — i.e. whether
   * the *next* fetch still carries `query` and can therefore rank by tag/semantic match. The
   * backend's gate (`resolve_search_gate`) ignores `filters` entirely whenever `query` is set,
   * so any filter/facet edit — not just an explicit removal — has to drop the concept to let
   * the edit take effect. */
  conceptActive: boolean;
  filters: Filters;
  facets: Facets;
  limit: number;
  offset: number;
}

export const DEFAULT_LIMIT = 30;

export const initialSearchState: SearchState = {
  query: null,
  lastQuery: "",
  conceptActive: false,
  filters: EMPTY_FILTERS,
  facets: EMPTY_FACETS,
  limit: DEFAULT_LIMIT,
  offset: 0,
};

export type SearchAction =
  // The NL box was submitted — a fresh query replaces the whole panel (filters + facets)
  // rather than compounding with whatever was there before.
  | { type: "query-submitted"; query: string }
  // The backend parsed `query` into a gate — ticks the panel's controls on and stops
  // resending `query`, so subsequent edits never re-invoke the parser.
  | { type: "query-resolved"; filters: Filters }
  // A chip/facet edit — patches filter state directly, no re-parse.
  | { type: "filter-changed"; patch: Partial<Filters> }
  | { type: "facet-changed"; patch: Partial<Facets> }
  | { type: "page-changed"; offset: number }
  // The user dismissed the concept indicator — drops semantic/tag ranking, keeps the
  // filters the parse already ticked on, and falls back to plain filter/browse.
  | { type: "concept-removed" };

export function searchStateReducer(state: SearchState, action: SearchAction): SearchState {
  switch (action.type) {
    case "query-submitted":
      return {
        ...state,
        query: action.query,
        lastQuery: action.query,
        conceptActive: true,
        filters: EMPTY_FILTERS,
        facets: {},
        offset: 0,
      };
    case "query-resolved":
      return {
        ...state,
        query: null,
        filters: action.filters,
      };
    case "filter-changed":
      return {
        ...state,
        query: null,
        conceptActive: false,
        filters: { ...state.filters, ...action.patch },
        offset: 0,
      };
    case "facet-changed":
      return {
        ...state,
        query: null,
        conceptActive: false,
        facets: { ...state.facets, ...action.patch },
        offset: 0,
      };
    case "page-changed":
      return { ...state, offset: action.offset };
    case "concept-removed":
      return { ...state, query: null, conceptActive: false };
  }
}
