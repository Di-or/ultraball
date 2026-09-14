import type { DeckLine } from "../state/deckState";

// Client-side PTCGL export (issue #31) — the mirror of the server's lenient reader in
// app/catalog/ptcgl_import.py. Writing is strict: every line carries its set code + local
// id, including basic Energy, so a round trip through `/decks/import` resolves exactly.

const SECTION_HEADINGS: Record<string, string> = {
  Pokemon: "Pokémon",
  Trainer: "Trainer Cards",
  Energy: "Energy",
};

const SECTION_ORDER = ["Pokemon", "Trainer", "Energy"];

export function exportToPtcgl(lines: DeckLine[]): string {
  const sections: string[] = [];
  let total = 0;

  for (const category of SECTION_ORDER) {
    const linesInSection = lines
      .filter((line) => line.category === category)
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name));
    if (linesInSection.length === 0) continue;

    const count = linesInSection.reduce((sum, line) => sum + line.count, 0);
    total += count;

    const body = linesInSection
      .map((line) => `${line.count} ${line.name} ${line.set_code} ${line.local_id}`)
      .join("\n");
    sections.push(`${SECTION_HEADINGS[category]}: ${count}\n\n${body}`);
  }

  sections.push(`Total Cards: ${total}`);
  return sections.join("\n\n");
}
