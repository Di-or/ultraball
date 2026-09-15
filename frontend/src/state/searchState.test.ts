import { describe, expect, it } from "vitest";
import { initialSearchState, searchStateReducer } from "./searchState";

describe("searchStateReducer", () => {
  it("submitting a fresh NL query resets filters/facets/offset and stages the query to send once", () => {
    const withPriorFacets = searchStateReducer(initialSearchState, {
      type: "facet-changed",
      patch: { rarity: ["Rare"] },
    });
    const withPriorPage = searchStateReducer(withPriorFacets, { type: "page-changed", offset: 30 });

    const next = searchStateReducer(withPriorPage, {
      type: "query-submitted",
      query: "energy acceleration under 130 HP",
    });

    expect(next.query).toBe("energy acceleration under 130 HP");
    expect(next.lastQuery).toBe("energy acceleration under 130 HP");
    expect(next.filters).toEqual(initialSearchState.filters);
    expect(next.facets).toEqual({});
    expect(next.offset).toBe(0);
  });

  it("resolving the parse ticks the panel's filters on and clears the pending query", () => {
    const submitted = searchStateReducer(initialSearchState, {
      type: "query-submitted",
      query: "energy acceleration under 130 HP",
    });

    const next = searchStateReducer(submitted, {
      type: "query-resolved",
      filters: { format: "standard", hp: { lte: 130 } },
    });

    expect(next.query).toBeNull();
    expect(next.lastQuery).toBe("energy acceleration under 130 HP");
    expect(next.filters).toEqual({ format: "standard", hp: { lte: 130 } });
  });

  it("patches filters directly on a chip/facet edit and clears any pending query so it never re-parses", () => {
    const resolved = searchStateReducer(
      searchStateReducer(initialSearchState, { type: "query-submitted", query: "acceleration" }),
      { type: "query-resolved", filters: { format: "standard", category: "Pokemon" } }
    );

    const next = searchStateReducer(resolved, {
      type: "filter-changed",
      patch: { stage: "Basic" },
    });

    expect(next.query).toBeNull();
    expect(next.lastQuery).toBe("acceleration");
    expect(next.filters).toEqual({ format: "standard", category: "Pokemon", stage: "Basic" });
  });

  it("merges facet edits and resets the page", () => {
    const paged = searchStateReducer(initialSearchState, { type: "page-changed", offset: 30 });

    const next = searchStateReducer(paged, {
      type: "facet-changed",
      patch: { regulation_mark: ["G", "H"] },
    });

    expect(next.facets).toEqual({ regulation_mark: ["G", "H"] });
    expect(next.offset).toBe(0);
  });

  it("resets the offset on any filter change", () => {
    const paged = searchStateReducer(initialSearchState, { type: "page-changed", offset: 60 });

    const next = searchStateReducer(paged, { type: "filter-changed", patch: { category: "Trainer" } });

    expect(next.offset).toBe(0);
  });

  it("updates only the offset on a page change", () => {
    const next = searchStateReducer(initialSearchState, { type: "page-changed", offset: 30 });

    expect(next.offset).toBe(30);
    expect(next.filters).toEqual(initialSearchState.filters);
  });

  it("clears a filter field when the patch sets it to null", () => {
    const seeded = searchStateReducer(initialSearchState, {
      type: "filter-changed",
      patch: { category: "Pokemon" },
    });

    const next = searchStateReducer(seeded, { type: "filter-changed", patch: { category: null } });

    expect(next.filters.category).toBeNull();
  });

  it("marks the concept active once a query is submitted", () => {
    const submitted = searchStateReducer(initialSearchState, {
      type: "query-submitted",
      query: "energy acceleration",
    });

    expect(submitted.conceptActive).toBe(true);
  });

  it("removing the concept indicator clears the query and drops semantic ranking without touching filters", () => {
    const resolved = searchStateReducer(
      searchStateReducer(initialSearchState, { type: "query-submitted", query: "energy acceleration" }),
      { type: "query-resolved", filters: { format: "standard", category: "Pokemon" } }
    );

    const next = searchStateReducer(resolved, { type: "concept-removed" });

    expect(next.conceptActive).toBe(false);
    expect(next.query).toBeNull();
    expect(next.filters).toEqual({ format: "standard", category: "Pokemon" });
  });

  it("drops the concept when a filter edit follows a resolved query (the gate ignores filters while query is set)", () => {
    const resolved = searchStateReducer(
      searchStateReducer(initialSearchState, { type: "query-submitted", query: "energy acceleration" }),
      { type: "query-resolved", filters: { format: "standard" } }
    );

    const next = searchStateReducer(resolved, { type: "filter-changed", patch: { stage: "Basic" } });

    expect(next.conceptActive).toBe(false);
  });

  it("drops the concept when a facet edit follows a resolved query", () => {
    const resolved = searchStateReducer(
      searchStateReducer(initialSearchState, { type: "query-submitted", query: "energy acceleration" }),
      { type: "query-resolved", filters: { format: "standard" } }
    );

    const next = searchStateReducer(resolved, { type: "facet-changed", patch: { rarity: ["Rare"] } });

    expect(next.conceptActive).toBe(false);
  });

  it("bumps fetchRevision on every fetch-worthy action, but query-resolved leaves it untouched", () => {
    // App.tsx keys its fetch effect off `fetchRevision` alone. `query-resolved` only
    // reconciles state from a response already in hand — bumping it here would cost App a
    // second, ranking-downgrading round trip (see the field's doc comment in searchState.ts).
    const submitted = searchStateReducer(initialSearchState, {
      type: "query-submitted",
      query: "acceleration",
    });
    expect(submitted.fetchRevision).toBe(initialSearchState.fetchRevision + 1);

    const resolved = searchStateReducer(submitted, {
      type: "query-resolved",
      filters: { format: "standard" },
    });
    expect(resolved.fetchRevision).toBe(submitted.fetchRevision);

    const removed = searchStateReducer(resolved, { type: "concept-removed" });
    expect(removed.fetchRevision).toBe(resolved.fetchRevision + 1);

    const filtered = searchStateReducer(removed, { type: "filter-changed", patch: { category: "Pokemon" } });
    expect(filtered.fetchRevision).toBe(removed.fetchRevision + 1);

    const faceted = searchStateReducer(filtered, { type: "facet-changed", patch: { rarity: ["Rare"] } });
    expect(faceted.fetchRevision).toBe(filtered.fetchRevision + 1);

    const paged = searchStateReducer(faceted, { type: "page-changed", offset: 30 });
    expect(paged.fetchRevision).toBe(faceted.fetchRevision + 1);
  });
});
