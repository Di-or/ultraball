import { describe, expect, it } from "vitest";
// A decklist exported by Limitless's deckbuilder that PTCGL imported cleanly (issue #123).
// The backend imports the same file (tests/test_ptcgl_real_export.py), so the two together
// check the round trip.
import ptcglCompatibleExport from "../../../tests/fixtures/ptcgl/limitless_export.txt?raw";
// Every Classic Collection card PTCGL lists and the three RGB Mews, copied from PTCGL (issue #123).
import classicCollectionExport from "../../../tests/fixtures/ptcgl/classic_collection_export.txt?raw";
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

  it("writes Classic Collection cards as PTCGL does", () => {
    // Copied from a real PTCGL export. The catalog stores the printed `CC` number; TCGdex
    // writes the name "Solgaleo GX".
    const deck = [
      pokemon("30th-c-024", 1, "Shining Celebi", "30C", "CC6"),
      pokemon("30th-c-017", 1, "Solgaleo GX", "30C", "CC23"),
    ];

    expect(exportToPtcgl(deck)).toBe("Pokémon: 2\n1 Shining Celebi 30C CC6\n1 Solgaleo-GX 30C CC23");
  });

  it("hyphenates older GX and EX names but leaves modern ex alone", () => {
    const deck = [
      pokemon("30th-c-008", 1, "Pikachu & Zekrom GX", "30C", "CC25"),
      pokemon("30th-c-023", 1, "M Gardevoir EX", "30C", "CC21"),
      pokemon("sv03-125", 1, "Charizard ex", "OBF", "125"),
    ];

    expect(exportToPtcgl(deck)).toBe(
      "Pokémon: 3\n1 Pikachu & Zekrom-GX 30C CC25\n1 M Gardevoir-EX 30C CC21\n1 Charizard ex OBF 125",
    );
  });

  it("writes every Classic Collection card and RGB Mew exactly as PTCGL does", () => {
    // As the catalog stores them: TCGdex's names (Palkia's corrected by a catalog override),
    // the printed `CC` numbers, and the Mews' letter numbers.
    const cards: [string, string, string][] = [
      ["30th-c-014", "Pikachu", "CC1"],
      ["30th-c-001", "Charizard", "CC2"],
      ["30th-c-015", "Erika's Jigglypuff", "CC4"],
      ["30th-c-007", "Sneasel", "CC5"],
      ["30th-c-024", "Shining Celebi", "CC6"],
      ["30th-c-029", "Lugia", "CC7"],
      ["30th-c-002", "Delcatty", "CC8"],
      ["30th-c-006", "Dark Tyranitar", "CC9"],
      ["30th-c-025", "Scizor ex", "CC10"],
      ["30th-c-003", "Metagross", "CC11"],
      ["30th-c-022", "Palkia LV.X", "CC12"],
      ["30th-c-010", "Uxie", "CC13"],
      ["30th-c-011", "Crobat G", "CC14"],
      ["30th-c-018", "Gengar", "CC15"],
      ["30th-c-019", "Darkrai & Cresselia LEGEND", "CC16"],
      ["30th-c-020", "Darkrai & Cresselia LEGEND", "CC17"],
      ["30th-c-016", "Rayquaza EX", "CC19"],
      ["30th-c-004", "Genesect EX", "CC20"],
      ["30th-c-023", "M Gardevoir EX", "CC21"],
      ["30th-c-009", "Greninja BREAK", "CC22"],
      ["30th-c-017", "Solgaleo GX", "CC23"],
      ["30th-c-013", "Buzzwole GX", "CC24"],
      ["30th-c-008", "Pikachu & Zekrom GX", "CC25"],
      ["30th-c-028", "Zacian V", "CC26"],
      ["30th-c-012", "Raikou", "CC27"],
      ["30th-c-026", "Mew VMAX", "CC28"],
      ["30th-c-027", "Arceus VSTAR", "CC29"],
      ["30th-c-030", "Magikarp", "CC30"],
      ["30th-G", "Mew", "G"],
      ["30th-R", "Mew", "R"],
      ["30th-B", "Mew", "B"],
    ];
    const deck = cards.map(([printing_id, name, local_id]) => pokemon(printing_id, 1, name, "30C", local_id));

    expect(exportToPtcgl(deck)).toBe(`Pokémon: 31\n${classicCollectionExport.replace(/\r\n/g, "\n").trimEnd()}`);
  });

  it("keeps a local id of zero", () => {
    expect(exportToPtcgl([trainer("x-000", "Card", "XYZ", "000")])).toBe("Trainer: 1\n1 Card XYZ 0");
  });
});
