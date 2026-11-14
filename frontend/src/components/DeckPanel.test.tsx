import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import type { DeckLine } from "../state/deckState";
import { DeckPanel } from "./DeckPanel";

const charmander: DeckLine = {
  printing_id: "obf-10",
  count: 4,
  name: "Charmander",
  category: "Pokemon",
  set_code: "OBF",
  local_id: "10",
  energy_type: null,
};

describe("DeckPanel", () => {
  beforeEach(() => {
    vi.spyOn(api, "getEnergyBasics").mockResolvedValue({
      palette: [
        { printing_id: "mee-002", name: "Fire Energy", energy_type: "Basic", types: [], image: null, set_code: "MEE", local_id: "002" },
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

  it("renders grouped rows with a stepper that never blocks a high count", async () => {
    const dispatch = vi.fn();
    render(<DeckPanel lines={[charmander]} dispatch={dispatch} />);

    expect(screen.getByText("Charmander")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Card count"), { target: { value: "9" } });

    expect(dispatch).toHaveBeenCalledWith({ type: "count-changed", printing_id: "obf-10", count: 9 });
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
      expect.objectContaining({ type: "card-added", card: expect.objectContaining({ printing_id: "mee-002" }) })
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
        { printing_id: "obf-10", count: 4, name: "Charmander", category: "Pokemon", set_code: "OBF", local_id: "10", energy_type: null },
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

  it("shows which printing a row is, so two versions of one card read apart", () => {
    const secretRare: DeckLine = { ...charmander, printing_id: "sv03.5-168", count: 1, set_code: "MEW", local_id: "168" };
    render(<DeckPanel lines={[charmander, secretRare]} dispatch={vi.fn()} />);

    const rows = within(screen.getByRole("region", { name: "Pokémon deck rows" })).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("OBF 10");
    expect(rows[1]).toHaveTextContent("MEW 168");
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
