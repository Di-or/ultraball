import { DECK_CATEGORY_ORDER } from "./deckCategories";
import type { Category } from "./types";
import type { DeckLine } from "../state/deckState";

// Client-side PTCGL export (issues #31, #123) — the mirror of the server's lenient reader in
// app/catalog/ptcgl_import.py. Writing is strict and matches a decklist PTCGL imports cleanly
// (tests/fixtures/ptcgl/limitless_export.txt):
//
//   Pokémon: 9
//   2 Yanmega PR-SV 187
//
//   Energy: 13
//   1 Lightning Energy MEE 12
//
// Every line carries its set code + local id, including Basic Energy, so a round trip through
// `/decks/import` resolves exactly. Lines keep the deck's order.

const SECTION_HEADINGS: Record<Category, string> = {
  Pokemon: "Pokémon",
  Trainer: "Trainer",
  Energy: "Energy",
};

export function exportToPtcgl(lines: DeckLine[]): string {
  const sections: string[] = [];

  for (const category of DECK_CATEGORY_ORDER) {
    const linesInSection = lines.filter((line) => line.category === category);
    if (linesInSection.length === 0) continue;

    const count = linesInSection.reduce((sum, line) => sum + line.count, 0);
    const body = linesInSection
      .map((line) => `${line.count} ${ptcglName(line)} ${line.set_code} ${ptcglNumber(line.local_id)}`)
      .join("\n");
    sections.push(`${SECTION_HEADINGS[category]}: ${count}\n${body}`);
  }

  return sections.join("\n\n");
}

// TCGdex names some Basic Energy printings "Basic Lightning Energy"; PTCGL writes "Lightning Energy".
function ptcglName(line: DeckLine): string {
  return line.energy_type === "Basic" ? line.name.replace(/^Basic\s+/i, "") : line.name;
}

// TCGdex zero-pads card numbers ("007"); PTCGL doesn't ("MEP 7").
function ptcglNumber(localId: string): string {
  return localId.replace(/^0+(?=.)/, "");
}
