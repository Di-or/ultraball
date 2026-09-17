import { describe, expect, it } from "vitest";
import type { DeckLine } from "../state/deckState";
import { exportToPtcgl } from "./ptcgl";

describe("exportToPtcgl", () => {
  it("groups lines by category, sums section counts, and totals the deck", () => {
    const lines: DeckLine[] = [
      { printing_id: "obf-10", count: 4, name: "Charmander", category: "Pokemon", set_code: "OBF", local_id: "10", energy_type: null },
      { printing_id: "paf-80", count: 1, name: "Iono", category: "Trainer", set_code: "PAF", local_id: "80", energy_type: null },
      { printing_id: "base4-98", count: 8, name: "Fire Energy", category: "Energy", set_code: "BASE4", local_id: "98", energy_type: "Basic" },
    ];

    const text = exportToPtcgl(lines);

    expect(text).toContain("Pokémon: 4");
    expect(text).toContain("4 Charmander OBF 10");
    expect(text).toContain("Trainer Cards: 1");
    expect(text).toContain("1 Iono PAF 80");
    expect(text).toContain("Energy: 8");
    expect(text).toContain("8 Fire Energy BASE4 98");
    expect(text).toContain("Total Cards: 13");
  });

  it("omits empty sections", () => {
    const lines: DeckLine[] = [
      { printing_id: "obf-10", count: 60, name: "Charmander", category: "Pokemon", set_code: "OBF", local_id: "10", energy_type: null },
    ];

    const text = exportToPtcgl(lines);

    expect(text).not.toContain("Trainer Cards");
    expect(text).not.toContain("Energy:");
  });
});
