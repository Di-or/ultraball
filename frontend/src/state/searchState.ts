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
  /** Bumped by every action that should cause a new `/search` fetch. `query-resolved` is the
   * one exception — it only reconciles UI state from a response App already has in hand, so
   * it deliberately leaves this untouched: bumping it would cost a redundant round trip that
   * resends with `query: null` and silently downgrades the just-fetched conceptually-ranked
   * results to a plain filter/browse response (the gate ignores `filters` only when `query`
   * is set — see the `conceptActive` doc above — so a `query: null` re-request always takes
   * the plain path). */
  fetchRevision: number;
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
  fetchRevision: 0,
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

/** No Pokémon card is ACE SPEC, so the tag can never apply under Pokémon. */
function withoutAceSpecUnderPokemon(filters: Filters): Filters {
  if (filters.category !== "Pokemon") return filters;
  const kept = filters.sub_category?.filter((s) => s !== "ace-spec");
  const result: Filters = { ...filters };
  if (kept?.length) result.sub_category = kept;
  else delete result.sub_category;
  return result;
}

/** Drops filters that can't apply to `next.category` whenever the category differs from
 * `previous`, so a leftover Pokémon-only filter can't zero out a Trainer search. */
function clearInapplicableFilters(previous: Filters, next: Filters): Filters {
  const category = next.category ?? null;
  if (category === (previous.category ?? null) || category === null) {
    return withoutAceSpecUnderPokemon(next);
  }

  const cleared: Filters = { ...next };
  if (category === "Pokemon") {
    delete cleared.trainer_type;
    delete cleared.energy_type;
  } else {
    if (category === "Trainer") delete cleared.energy_type;
    else delete cleared.trainer_type;
    delete cleared.stage;
    delete cleared.types;
    delete cleared.hp;
    delete cleared.retreat;
    delete cleared.attack_cost;
    const kept = next.sub_category?.filter((s) => s === "ace-spec");
    if (kept?.length) cleared.sub_category = kept;
    else delete cleared.sub_category;
  }
  return withoutAceSpecUnderPokemon(cleared);
}

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
        fetchRevision: state.fetchRevision + 1,
      };
    case "query-resolved":
      // Deliberately does not bump `fetchRevision` — see the field's doc comment. The parse is
      // copied verbatim, not run through clearInapplicableFilters: those filters already drove
      // the fetch in hand, so trimming them would leave the panel disagreeing with the results.
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
        filters: clearInapplicableFilters(state.filters, { ...state.filters, ...action.patch }),
        offset: 0,
        fetchRevision: state.fetchRevision + 1,
      };
    case "facet-changed":
      return {
        ...state,
        query: null,
        conceptActive: false,
        facets: { ...state.facets, ...action.patch },
        offset: 0,
        fetchRevision: state.fetchRevision + 1,
      };
    case "page-changed":
      return { ...state, offset: action.offset, fetchRevision: state.fetchRevision + 1 };
    case "concept-removed":
      return { ...state, query: null, conceptActive: false, fetchRevision: state.fetchRevision + 1 };
  }
}
