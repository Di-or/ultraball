import { describe, expect, it } from "vitest";
import { deckStateReducer, initialDeckState, type DeckCardInput, type DeckLine } from "./deckState";

const charmander: DeckCardInput = {
  printing_id: "obf-10",
  name: "Charmander",
  category: "Pokemon",
  set_code: "OBF",
  local_id: "10",
  energy_type: null,
};

describe("deckStateReducer", () => {
  it("adds a new card as one copy", () => {
    const state = deckStateReducer(initialDeckState, { type: "card-added", card: charmander });

    expect(state.lines).toEqual([{ ...charmander, count: 1 }]);
  });

  it("increments an existing line instead of duplicating it", () => {
    let state = deckStateReducer(initialDeckState, { type: "card-added", card: charmander });
    state = deckStateReducer(state, { type: "card-added", card: charmander });

    expect(state.lines).toHaveLength(1);
    expect(state.lines[0].count).toBe(2);
  });

  it("sets an absolute count from a stepper edit, never blocking a high count", () => {
    let state = deckStateReducer(initialDeckState, { type: "card-added", card: charmander });
    state = deckStateReducer(state, { type: "count-changed", printing_id: "obf-10", count: 9 });

    expect(state.lines[0].count).toBe(9);
  });

  it("removes the line when a stepper edit brings the count to zero", () => {
    let state = deckStateReducer(initialDeckState, { type: "card-added", card: charmander });
    state = deckStateReducer(state, { type: "count-changed", printing_id: "obf-10", count: 0 });

    expect(state.lines).toEqual([]);
  });

  it("replaces the whole deck on import", () => {
    const imported: DeckLine[] = [{ ...charmander, count: 4 }];
    let state = deckStateReducer(initialDeckState, {
      type: "card-added",
      card: { ...charmander, printing_id: "different-card" },
    });
    state = deckStateReducer(state, { type: "deck-replaced", lines: imported });

    expect(state.lines).toEqual(imported);
  });
});
