import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import type { DeckLine } from "../state/deckState";
import { DeckPanel } from "./DeckPanel";

const OBF_10_ART = "https://assets.tcgdex.net/en/sv/sv03/010/low.webp";

const charmander: DeckLine = {
  printing_id: "obf-10",
  count: 4,
  name: "Charmander",
  category: "Pokemon",
  set_code: "OBF",
  local_id: "10",
  energy_type: null,
  image: OBF_10_ART,
};

function pokemonTiles() {
  return within(screen.getByRole("region", { name: "Pokémon deck cards" })).getAllByRole("listitem");
}

describe("DeckPanel", () => {
  beforeEach(() => {
    vi.spyOn(api, "getEnergyBasics").mockResolvedValue({
      palette: [
        { printing_id: "mee-002", name: "Fire Energy", energy_type: "Basic", types: [], image: "https://assets.tcgdex.net/en/me/mee/002/low.webp", set_code: "MEE", local_id: "002" },
      ],
    });
    vi.spyOn(api, "validateDeck").mockResolvedValue({
      legal: false,
      counts: { pokemon: 4, trainer: 0, energy: 0, total: 4 },
      violations: [{ code: "deck_size", message: "Deck has 4 cards, needs 60", cards: [] }],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows each deck line as one image tile with its art, a count badge and its set code and number", () => {
    render(<DeckPanel lines={[charmander]} dispatch={vi.fn()} />);

    const [tile] = pokemonTiles();
    expect(within(tile).getByRole("img", { name: "Charmander OBF 10" })).toHaveAttribute("src", OBF_10_ART);
    expect(within(tile).getByLabelText("4 copies")).toHaveTextContent("×4");
    expect(tile).toHaveTextContent("OBF 10");
  });

  it("steps a tile's count up and down, never blocking a count above four", () => {
    const dispatch = vi.fn();
    render(<DeckPanel lines={[charmander]} dispatch={dispatch} />);

    const [tile] = pokemonTiles();
    fireEvent.click(within(tile).getByRole("button", { name: "Add one Charmander OBF 10" }));
    expect(dispatch).toHaveBeenLastCalledWith({ type: "count-changed", printing_id: "obf-10", count: 5 });
    fireEvent.click(within(tile).getByRole("button", { name: "Remove one Charmander OBF 10" }));
    expect(dispatch).toHaveBeenLastCalledWith({ type: "count-changed", printing_id: "obf-10", count: 3 });
  });

  it("groups tiles into Pokémon, Trainer and Energy sections", () => {
    const iono: DeckLine = { ...charmander, printing_id: "sv02-185", name: "Iono", category: "Trainer", set_code: "PAL", local_id: "185" };
    render(<DeckPanel lines={[iono, charmander]} dispatch={vi.fn()} />);

    expect(pokemonTiles()).toHaveLength(1);
    const trainers = within(screen.getByRole("region", { name: "Trainer deck cards" })).getAllByRole("listitem");
    expect(trainers).toHaveLength(1);
    expect(trainers[0]).toHaveTextContent("PAL 185");
  });

  it("shows borrowed same-text art under the line's own set code and number", () => {
    // The backend hands an MEW 168 line the art of another printing with the same text.
    const borrowed: DeckLine = { ...charmander, printing_id: "sv03.5-168", set_code: "MEW", local_id: "168" };
    render(<DeckPanel lines={[borrowed]} dispatch={vi.fn()} />);

    const [tile] = pokemonTiles();
    expect(within(tile).getByRole("img", { name: "Charmander MEW 168" })).toHaveAttribute("src", OBF_10_ART);
    expect(tile).toHaveTextContent("MEW 168");
  });

  it("shows the card placeholder when no printing of the card has art", () => {
    render(<DeckPanel lines={[{ ...charmander, image: null }]} dispatch={vi.fn()} />);

    const [tile] = pokemonTiles();
    expect(within(tile).getByRole("img", { name: "Charmander OBF 10 (no image)" })).toBeInTheDocument();
    expect(within(tile).getByLabelText("4 copies")).toBeInTheDocument();
  });

  it("shows a Basic Energy tile as its Energy symbol", () => {
    const fire: DeckLine = {
      printing_id: "mee-002",
      count: 8,
      name: "Fire Energy",
      category: "Energy",
      set_code: "MEE",
      local_id: "2",
      energy_type: "Basic",
      image: null,
    };
    render(<DeckPanel lines={[fire]} dispatch={vi.fn()} />);

    const [tile] = within(screen.getByRole("region", { name: "Energy deck cards" })).getAllByRole("listitem");
    expect(within(tile).getByRole("img", { name: "Fire Energy" })).toBeInTheDocument();
    expect(within(tile).getByLabelText("8 copies")).toHaveTextContent("×8");
    expect(tile).toHaveTextContent("MEE 2");
  });

  it("shows the debounced legality readout and violations", async () => {
    render(<DeckPanel lines={[charmander]} dispatch={vi.fn()} />);

    await waitFor(() => expect(screen.getByLabelText("Not legal")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.getByText("Deck has 4 cards, needs 60")).toBeInTheDocument();
    expect(screen.getByText("4/60")).toBeInTheDocument();
  });

  it("adds a basic energy from the tray", async () => {
    const dispatch = vi.fn();
    render(<DeckPanel lines={[]} dispatch={dispatch} />);

    const button = await screen.findByRole("button", { name: "Fire Energy" });
    fireEvent.click(button);

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "card-added",
        card: expect.objectContaining({ printing_id: "mee-002", image: "https://assets.tcgdex.net/en/me/mee/002/low.webp" }),
      })
    );
  });

  it("shows each tray button as its Energy symbol plus the type name", async () => {
    render(<DeckPanel lines={[]} dispatch={vi.fn()} />);

    const button = await screen.findByRole("button", { name: "Fire Energy" });
    expect(within(button).getByRole("img", { name: "Fire Energy" })).toBeInTheDocument();
    expect(within(button).getByText("Fire")).toBeInTheDocument();
  });

  it("imports a decklist and replaces the deck", async () => {
    const dispatch = vi.fn();
    vi.spyOn(api, "importDeck").mockResolvedValue({
      entries: [
        { printing_id: "obf-10", count: 4, name: "Charmander", category: "Pokemon", set_code: "OBF", local_id: "10", energy_type: null, image: OBF_10_ART },
      ],
    });
    render(<DeckPanel lines={[]} dispatch={dispatch} />);

    fireEvent.change(screen.getByLabelText("PTCGL decklist"), { target: { value: "4 Charmander OBF 10" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() =>
      expect(dispatch).toHaveBeenCalledWith({
        type: "deck-replaced",
        lines: [charmander],
      })
    );
  });

  it("surfaces unresolved lines when import is rejected", async () => {
    vi.spyOn(api, "importDeck").mockRejectedValue(
      new api.DeckImportRejected({ message: "bad", lines: ["2 Not A Real Card XYZ 999"] })
    );
    render(<DeckPanel lines={[]} dispatch={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("PTCGL decklist"), { target: { value: "2 Not A Real Card XYZ 999" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("2 Not A Real Card XYZ 999")
    );
  });

  it("gives each printing of one card its own tile, so two versions read apart", () => {
    const secretRare: DeckLine = { ...charmander, printing_id: "sv03.5-168", count: 1, set_code: "MEW", local_id: "168" };
    render(<DeckPanel lines={[charmander, secretRare]} dispatch={vi.fn()} />);

    const tiles = pokemonTiles();
    expect(tiles).toHaveLength(2);
    expect(tiles[0]).toHaveTextContent("OBF 10");
    expect(tiles[1]).toHaveTextContent("MEW 168");
  });

  it("exports a chosen printing with its own set code and number", () => {
    const secretRare: DeckLine = { ...charmander, printing_id: "sv03.5-168", count: 1, set_code: "MEW", local_id: "168" };
    render(<DeckPanel lines={[charmander, secretRare]} dispatch={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Export to PTCGL" }));

    const textarea = screen.getByLabelText("PTCGL export") as HTMLTextAreaElement;
    expect(textarea.value).toContain("4 Charmander OBF 10");
    expect(textarea.value).toContain("1 Charmander MEW 168");
  });

  it("exports the deck to PTCGL text", () => {
    render(<DeckPanel lines={[charmander]} dispatch={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Export to PTCGL" }));

    const textarea = screen.getByLabelText("PTCGL export") as HTMLTextAreaElement;
    expect(textarea.value).toContain("4 Charmander OBF 10");
  });
});
