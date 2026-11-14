import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CardDetailModal } from "./CardDetailModal";
import type { CardDetail } from "../lib/types";

function detailResponse(body: CardDetail): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

const CHARIZARD: CardDetail = {
  dedupe_key: "charizard",
  printing_id: "swsh4-1",
  name: "Charizard",
  category: "Pokemon",
  hp: 170,
  types: ["Fire"],
  stage: "Stage 2",
  evolve_from: "Charmeleon",
  retreat: 3,
  regulation_mark: "F",
  rarity: "Rare Holo",
  set_id: "swsh4",
  sub_category: [],
  trainer_type: null,
  energy_type: null,
  attacks: [{ name: "Fire Spin", cost: ["Fire", "Fire", "Colorless", "Colorless"], damage: 120, effect: "Discard 2 Energy." }],
  abilities: [],
  attack_costs: [4],
  image: "https://assets.tcgdex.net/en/swsh/swsh4/1/high.webp",
  is_standard_legal: false,
  tags: ["acceleration"],
  printings: [
    { printing_id: "swsh4-1", set_id: "swsh4", set_code: "VIV", local_id: "025", regulation_mark: "F", rarity: "Rare Holo", image: null, is_standard_legal: false },
    { printing_id: "swsh1-1", set_id: "swsh1", set_code: "SSH", local_id: "1", regulation_mark: "D", rarity: "Secret Rare", image: null, is_standard_legal: false },
  ],
  matched: { tags: ["acceleration"], semantic: true },
};

describe("CardDetailModal", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches by printing id and renders the card's printed info, tags, printings, and matched chip", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(detailResponse(CHARIZARD));

    render(<CardDetailModal printingId="swsh4-1" onClose={vi.fn()} onAddToDeck={vi.fn()} />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "Charizard" })).toBeInTheDocument());

    expect(fetch).toHaveBeenCalledWith("/cards/swsh4-1", expect.anything());
    expect(screen.getByText(/170 HP/)).toBeInTheDocument();
    expect(screen.getByText(/Fire Spin/)).toBeInTheDocument();
    expect(screen.getAllByText("acceleration").length).toBeGreaterThan(0);
    expect(screen.getByText(/VIV 25/)).toBeInTheDocument();
    expect(screen.getByText(/SSH 1/)).toBeInTheDocument();
  });

  it("shows the card's art from the URL the API gives, wherever it is hosted", async () => {
    const art = "https://images.example.com/charizard.png";
    vi.mocked(fetch).mockResolvedValueOnce(detailResponse({ ...CHARIZARD, image: art }));

    render(<CardDetailModal printingId="swsh4-1" onClose={vi.fn()} onAddToDeck={vi.fn()} />);

    expect(await screen.findByRole("img", { name: "Charizard" })).toHaveAttribute("src", art);
  });

  it("shows a placeholder with the card name in the header when no printing has art", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(detailResponse({ ...CHARIZARD, image: null }));

    render(<CardDetailModal printingId="swsh4-1" onClose={vi.fn()} onAddToDeck={vi.fn()} />);

    // The header art is the card's (borrowed from any printing), so no one set code is meant.
    expect(await screen.findByRole("img", { name: "Charizard (no image)" })).toHaveTextContent(/^Charizard$/);
    expect(screen.queryByRole("img", { name: "Charizard" })).not.toBeInTheDocument();
  });

  it("passes matched provenance through as query params", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(detailResponse(CHARIZARD));

    render(
      <CardDetailModal
        printingId="swsh4-1"
        matched={{ tags: ["acceleration"], semantic: true }}
        onClose={vi.fn()}
        onAddToDeck={vi.fn()}
      />
    );

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).toContain("matched_tags=acceleration");
    expect(url).toContain("matched_semantic=true");
  });

  it("adds the chosen printing, not the representative, from its own 'add this version' control", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(detailResponse(CHARIZARD));
    const onAddToDeck = vi.fn();

    render(<CardDetailModal printingId="swsh4-1" onClose={vi.fn()} onAddToDeck={onAddToDeck} />);

    const printings = await screen.findByRole("list", { name: "Printings" });
    const secretRare = within(printings).getByText(/Secret Rare/).closest("li")!;
    fireEvent.click(within(secretRare).getByRole("button", { name: /Add this version/ }));

    expect(onAddToDeck).toHaveBeenCalledTimes(1);
    expect(onAddToDeck).toHaveBeenCalledWith({
      printing_id: "swsh1-1",
      name: "Charizard",
      category: "Pokemon",
      set_code: "SSH",
      local_id: "1",
      energy_type: null,
    });
  });

  it("shows how many copies of each printing are already in the deck, beside its add control", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(detailResponse(CHARIZARD));

    render(
      <CardDetailModal printingId="swsh4-1" onClose={vi.fn()} onAddToDeck={vi.fn()} deckCounts={{ "swsh1-1": 2 }} />
    );

    const printings = await screen.findByRole("list", { name: "Printings" });
    const secretRare = within(printings).getByText(/Secret Rare/).closest("li")!;
    const holo = within(printings).getByText(/VIV 25/).closest("li")!;
    expect(within(secretRare).getByText("In deck: 2")).toBeInTheDocument();
    expect(within(holo).queryByText(/In deck/)).not.toBeInTheDocument();
  });

  it("offers one 'add this version' control per printing", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(detailResponse(CHARIZARD));

    render(<CardDetailModal printingId="swsh4-1" onClose={vi.fn()} onAddToDeck={vi.fn()} />);

    const printings = await screen.findByRole("list", { name: "Printings" });
    expect(within(printings).getAllByRole("button", { name: /Add this version/ })).toHaveLength(2);
    expect(within(printings).getByText(/VIV 25/)).toBeInTheDocument();
  });

  it("closes on backdrop click, close button, and Escape", async () => {
    vi.mocked(fetch).mockResolvedValue(detailResponse(CHARIZARD));
    const onClose = vi.fn();
    const { container, rerender } = render(<CardDetailModal printingId="swsh4-1" onClose={onClose} onAddToDeck={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole("heading", { name: "Charizard" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).toHaveBeenCalledTimes(1); // clicking inside the dialog itself does not close it

    fireEvent.click(container.querySelector(".modal-backdrop")!);
    expect(onClose).toHaveBeenCalledTimes(2);

    rerender(<CardDetailModal printingId="swsh4-1" onClose={onClose} onAddToDeck={vi.fn()} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(3);
  });
});
