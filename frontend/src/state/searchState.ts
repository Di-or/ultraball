import { EMPTY_FACETS, EMPTY_FILTERS, type Facets, type Filters } from "../lib/types";

export interface SearchState {
  /** Set only right after an NL submit; the effect sends it once, then clears it on
   * resolution so a later filter/facet edit never re-triggers a parse. */
  query: string | null;
  /** The last submitted NL text, kept only for display in the search box / concept indicator. */
  lastQuery: string;
  filters: Filters;
  facets: Facets;
  limit: number;
  offset: number;
}

export const DEFAULT_LIMIT = 30;

export const initialSearchState: SearchState = {
  query: null,
  lastQuery: "",
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
  | { type: "page-changed"; offset: number };

export function searchStateReducer(state: SearchState, action: SearchAction): SearchState {
  switch (action.type) {
    case "query-submitted":
      return {
        ...state,
        query: action.query,
        lastQuery: action.query,
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
        filters: { ...state.filters, ...action.patch },
        offset: 0,
      };
    case "facet-changed":
      return {
        ...state,
        query: null,
        facets: { ...state.facets, ...action.patch },
        offset: 0,
      };
    case "page-changed":
      return { ...state, offset: action.offset };
  }
}
