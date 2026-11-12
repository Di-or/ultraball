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
      .map((line) => `${line.count} ${ptcglName(line)} ${printingLabel(line.set_code, line.local_id)}`)
      .join("\n");
    sections.push(`${SECTION_HEADINGS[category]}: ${count}\n${body}`);
  }

  return sections.join("\n\n");
}

// TCGdex names some Basic Energy printings "Basic Lightning Energy"; PTCGL writes "Lightning Energy".
// TCGdex writes older rule boxes as "Solgaleo GX" / "M Gardevoir EX"; PTCGL hyphenates them
// ("Solgaleo-GX"). Modern lowercase "ex" ("Charizard ex") has no hyphen.
function ptcglName(line: DeckLine): string {
  const name = line.energy_type === "Basic" ? line.name.replace(/^Basic\s+/i, "") : line.name;
  return name.replace(/ (GX|EX)$/, "-$1");
}

// A printing's set code + number as PTCGL writes it ("OBF 125") — the export's tail, and the
// label card detail and the deck panel show, so what the player picks is what gets exported.
export function printingLabel(setCode: string, localId: string): string {
  return `${setCode} ${ptcglNumber(localId)}`;
}

// TCGdex zero-pads card numbers ("007"); PTCGL doesn't ("MEP 7").
function ptcglNumber(localId: string): string {
  return localId.replace(/^0+(?=.)/, "");
}
