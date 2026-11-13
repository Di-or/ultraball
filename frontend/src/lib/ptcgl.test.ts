import { describe, expect, it } from "vitest";
// A decklist exported by Limitless's deckbuilder that PTCGL imported cleanly (issue #123).
// The backend imports the same file (tests/test_ptcgl_real_export.py), so the two together
// check the round trip.
import ptcglCompatibleExport from "../../../tests/fixtures/ptcgl/limitless_export.txt?raw";
import type { DeckLine } from "../state/deckState";
import { exportToPtcgl } from "./ptcgl";

// That deck as the app holds it: TCGdex's names and zero-padded local ids, set codes as the
// catalog derives them (`svp` is `PR-SV`), in the order the cards were added.
const pokemon = (printing_id: string, count: number, name: string, set_code: string, local_id: string): DeckLine => ({
  printing_id,
  count,
  name,
  category: "Pokemon",
  set_code,
  local_id,
  energy_type: null,
});
const trainer = (printing_id: string, name: string, set_code: string, local_id: string): DeckLine => ({
  printing_id,
  count: 1,
  name,
  category: "Trainer",
  set_code,
  local_id,
  energy_type: null,
});
const energy = (
  printing_id: string,
  count: number,
  name: string,
  set_code: string,
  local_id: string,
  energy_type: "Basic" | "Special",
): DeckLine => ({ printing_id, count, name, category: "Energy", set_code, local_id, energy_type });

const DECK: DeckLine[] = [
  pokemon("mep-007", 2, "Psyduck", "MEP", "007"),
  pokemon("mep-020", 2, "Sneasel", "MEP", "020"),
  pokemon("svp-187", 2, "Yanmega", "PR-SV", "187"),
  pokemon("svp-202", 1, "Kangaskhan", "PR-SV", "202"),
  pokemon("mep-010", 1, "Riolu", "MEP", "010"),
  pokemon("mep-034", 1, "Mega Meganium ex", "MEP", "034"),
  trainer("me05-080", "Misty's Vitality", "PBL", "080"),
  trainer("me02.5-181", "Air Balloon", "ASC", "181"),
  trainer("sv06.5-055", "Binding Mochi", "SFA", "055"),
  trainer("sv06.5-054", "Academy at Night", "SFA", "054"),
  trainer("sv06.5-060", "Neutralization Zone", "SFA", "060"),
  trainer("sv06-145", "Carmine", "TWM", "145"),
  energy("sve-001", 1, "Grass Energy", "SVE", "001", "Basic"),
  energy("sve-002", 2, "Fire Energy", "SVE", "002", "Basic"),
  energy("sve-003", 2, "Water Energy", "SVE", "003", "Basic"),
  energy("mee-004", 1, "Lightning Energy", "MEE", "004", "Basic"),
  energy("mee-005", 1, "Psychic Energy", "MEE", "005", "Basic"),
  energy("mee-006", 1, "Fighting Energy", "MEE", "006", "Basic"),
  energy("mee-007", 1, "Darkness Energy", "MEE", "007", "Basic"),
  energy("mee-008", 1, "Metal Energy", "MEE", "008", "Basic"),
  // TCGdex names this printing "Basic Lightning Energy"; PTCGL writes "Lightning Energy".
  energy("mee-012", 1, "Basic Lightning Energy", "MEE", "012", "Basic"),
  energy("sv05-161", 1, "Mist Energy", "TEF", "161", "Special"),
  energy("me04-084", 1, "Bubbly Water Energy", "CRI", "084", "Special"),
];

describe("exportToPtcgl", () => {
  it("writes a deck exactly as a PTCGL-compatible export does", () => {
    expect(exportToPtcgl(DECK)).toBe(ptcglCompatibleExport.replace(/\r\n/g, "\n").trimEnd());
  });

  it("omits empty sections", () => {
    const text = exportToPtcgl([pokemon("mep-007", 60, "Psyduck", "MEP", "007")]);

    expect(text).toBe("Pokémon: 60\n60 Psyduck MEP 7");
  });

  it("writes a 30th Celebration card as PTCGL does", () => {
    // Copied from a real PTCGL export.
    expect(exportToPtcgl([pokemon("30th-017", 1, "Lapras", "30C", "017")])).toBe("Pokémon: 1\n1 Lapras 30C 17");
  });

  it("hyphenates older GX and EX names but leaves modern ex alone", () => {
    const deck = [
      pokemon("x-001", 1, "Pikachu & Zekrom GX", "XYZ", "001"),
      pokemon("x-002", 1, "M Gardevoir EX", "XYZ", "002"),
      pokemon("sv03-125", 1, "Charizard ex", "OBF", "125"),
    ];

    expect(exportToPtcgl(deck)).toBe(
      "Pokémon: 3\n1 Pikachu & Zekrom-GX XYZ 1\n1 M Gardevoir-EX XYZ 2\n1 Charizard ex OBF 125",
    );
  });

  it("writes the RGB Mews by their letter numbers as PTCGL does", () => {
    // Copied from a real PTCGL export.
    const deck = ["G", "R", "B"].map((letter) => pokemon(`30th-${letter}`, 1, "Mew", "30C", letter));

    expect(exportToPtcgl(deck)).toBe("Pokémon: 3\n1 Mew 30C G\n1 Mew 30C R\n1 Mew 30C B");
  });

  it("keeps a local id of zero", () => {
    expect(exportToPtcgl([trainer("x-000", "Card", "XYZ", "000")])).toBe("Trainer: 1\n1 Card XYZ 0");
  });
});
