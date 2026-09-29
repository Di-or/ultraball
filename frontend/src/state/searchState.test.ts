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

  describe("changing category clears filters that can't apply", () => {
    const pokemonFilters = {
      format: "standard" as const,
      category: "Pokemon" as const,
      stage: "Basic" as const,
      types: ["Fire"],
      hp: { gte: 100 },
      retreat: { lte: 2 },
      attack_cost: { lte: 3 },
      sub_category: ["ex" as const, "mega" as const, "ace-spec" as const],
      set_id: "sv1",
    };
    const seed = (filters: typeof pokemonFilters | Record<string, unknown>) => ({
      ...initialSearchState,
      filters: filters as typeof pokemonFilters,
    });

    it("switching to Trainer clears the Pokemon-only fields but keeps ACE SPEC and unrelated fields", () => {
      const next = searchStateReducer(seed(pokemonFilters), {
        type: "filter-changed",
        patch: { category: "Trainer" },
      });

      expect(next.filters).toEqual({
        format: "standard",
        category: "Trainer",
        sub_category: ["ace-spec"],
        set_id: "sv1",
      });
    });

    it("switching to Energy clears the Pokemon-only fields but keeps ACE SPEC", () => {
      const next = searchStateReducer(seed(pokemonFilters), {
        type: "filter-changed",
        patch: { category: "Energy" },
      });

      expect(next.filters).toEqual({
        format: "standard",
        category: "Energy",
        sub_category: ["ace-spec"],
        set_id: "sv1",
      });
    });

    it("drops sub_category entirely when only ex/Mega were set", () => {
      const next = searchStateReducer(seed({ category: "Pokemon", sub_category: ["ex", "mega"] }), {
        type: "filter-changed",
        patch: { category: "Trainer" },
      });

      expect(next.filters.sub_category ?? null).toBeNull();
    });

    it("switching to Pokemon drops ACE SPEC but keeps a sub-category chosen in the same edit", () => {
      const next = searchStateReducer(
        seed({ format: "standard", category: "Trainer", trainer_type: "Item", sub_category: ["ace-spec"] }),
        { type: "filter-changed", patch: { category: "Pokemon", sub_category: ["ace-spec", "ex"] } }
      );

      expect(next.filters).toEqual({ format: "standard", category: "Pokemon", sub_category: ["ex"] });
    });

    it("a stage chip click after a Trainer search clears the trainer type", () => {
      const next = searchStateReducer(
        seed({ format: "standard", category: "Trainer", trainer_type: "Supporter" }),
        { type: "filter-changed", patch: { category: "Pokemon", stage: "Basic" } }
      );

      expect(next.filters).toEqual({ format: "standard", category: "Pokemon", stage: "Basic" });
    });

    it("switching to Pokemon clears trainer type and energy type", () => {
      const next = searchStateReducer(
        seed({ format: "standard", category: "Trainer", trainer_type: "Supporter", energy_type: "Fire" }),
        { type: "filter-changed", patch: { category: "Pokemon" } }
      );

      expect(next.filters).toEqual({ format: "standard", category: "Pokemon" });
    });

    it("switching to Any clears nothing", () => {
      const next = searchStateReducer(seed(pokemonFilters), {
        type: "filter-changed",
        patch: { category: null },
      });

      expect(next.filters).toEqual({ ...pokemonFilters, category: null });
    });

    it("re-selecting the same category clears nothing", () => {
      const next = searchStateReducer(seed(pokemonFilters), {
        type: "filter-changed",
        patch: { category: "Pokemon" },
      });

      expect(next.filters).toEqual(pokemonFilters);
    });

    it("editing a field without changing the category clears nothing", () => {
      const next = searchStateReducer(seed(pokemonFilters), {
        type: "filter-changed",
        patch: { stage: "Stage 1" },
      });

      expect(next.filters).toEqual({ ...pokemonFilters, stage: "Stage 1" });
    });

    it("a combined category-plus-field edit keeps its field", () => {
      const next = searchStateReducer(seed(pokemonFilters), {
        type: "filter-changed",
        patch: { category: "Trainer", trainer_type: "Supporter" },
      });

      expect(next.filters.category).toBe("Trainer");
      expect(next.filters.trainer_type).toBe("Supporter");
      expect(next.filters.hp ?? null).toBeNull();
    });

    it("switching from Trainer to Energy clears trainer type but keeps energy type", () => {
      const next = searchStateReducer(
        seed({ category: "Trainer", trainer_type: "Supporter", energy_type: "Fire" }),
        { type: "filter-changed", patch: { category: "Energy" } }
      );

      expect(next.filters.trainer_type ?? null).toBeNull();
      expect(next.filters.energy_type).toBe("Fire");
    });

    it("switching from Energy to Trainer clears energy type but keeps trainer type", () => {
      const next = searchStateReducer(
        seed({ category: "Energy", trainer_type: "Supporter", energy_type: "Fire" }),
        { type: "filter-changed", patch: { category: "Trainer" } }
      );

      expect(next.filters.energy_type ?? null).toBeNull();
      expect(next.filters.trainer_type).toBe("Supporter");
    });

    it("switching from Energy to Pokemon clears energy type", () => {
      const next = searchStateReducer(seed({ category: "Energy", energy_type: "Fire" }), {
        type: "filter-changed",
        patch: { category: "Pokemon" },
      });

      expect(next.filters.energy_type ?? null).toBeNull();
    });

    it("a parsed query's filters are copied as-is so the panel matches the results already fetched", () => {
      const submitted = searchStateReducer(seed(pokemonFilters), {
        type: "query-submitted",
        query: "supporter draw",
      });
      const parsed = { format: "standard" as const, category: "Trainer" as const, hp: { lte: 100 } };

      const resolved = searchStateReducer(submitted, { type: "query-resolved", filters: parsed });

      expect(resolved.filters).toEqual(parsed);
    });

    it("clicking Supporter after setting an HP range clears the HP range", () => {
      const next = searchStateReducer(seed({ category: "Pokemon", hp: { gte: 100 } }), {
        type: "filter-changed",
        patch: { category: "Trainer", trainer_type: "Supporter" },
      });

      expect(next.filters.hp ?? null).toBeNull();
      expect(next.filters.category).toBe("Trainer");
      expect(next.filters.trainer_type).toBe("Supporter");
    });

    it("toggling ACE SPEC with no category set leaves Category unset", () => {
      const next = searchStateReducer(seed({ format: "standard" }), {
        type: "filter-changed",
        patch: { sub_category: ["ace-spec"] },
      });

      expect(next.filters.category ?? null).toBeNull();
      expect(next.filters.sub_category).toEqual(["ace-spec"]);
    });

    it("picking Item with ACE SPEC already on keeps both, so the search finds ACE SPEC Items", () => {
      const next = searchStateReducer(seed({ sub_category: ["ace-spec"] }), {
        type: "filter-changed",
        patch: { category: "Trainer", trainer_type: "Item" },
      });

      expect(next.filters.category).toBe("Trainer");
      expect(next.filters.trainer_type).toBe("Item");
      expect(next.filters.sub_category).toEqual(["ace-spec"]);
    });

    it("clicking Special Energy from a Pokémon search clears Pokémon filters and keeps energy type", () => {
      const next = searchStateReducer(seed({ category: "Pokemon", hp: { gte: 100 }, stage: "Basic" }), {
        type: "filter-changed",
        patch: { category: "Energy", energy_type: "Special" },
      });

      expect(next.filters.hp ?? null).toBeNull();
      expect(next.filters.stage ?? null).toBeNull();
      expect(next.filters.energy_type).toBe("Special");
    });
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
