import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CardDetailModal } from "./CardDetailModal";
import type { CardDetail } from "../lib/types";

function detailResponse(body: CardDetail): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

const CHARIZARD: CardDetail = {
  entity_id: "charizard",
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
  image: "https://assets.tcgdex.net/en/swsh/swsh4/1",
  is_standard_legal: false,
  tags: ["acceleration"],
  printings: [
    { printing_id: "swsh4-1", set_id: "swsh4", regulation_mark: "F", rarity: "Rare Holo", image: null, is_standard_legal: false },
    { printing_id: "swsh1-1", set_id: "swsh1", regulation_mark: "D", rarity: "Rare Holo", image: null, is_standard_legal: false },
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

  it("fetches and renders the card's printed info, tags, printings, and matched chip", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(detailResponse(CHARIZARD));

    render(<CardDetailModal entityId="charizard" onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "Charizard" })).toBeInTheDocument());

    expect(fetch).toHaveBeenCalledWith("/cards/charizard", expect.anything());
    expect(screen.getByText(/170 HP/)).toBeInTheDocument();
    expect(screen.getByText(/Fire Spin/)).toBeInTheDocument();
    expect(screen.getAllByText("acceleration").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/swsh4|swsh1/).length).toBeGreaterThan(0);
  });

  it("passes matched provenance through as query params", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(detailResponse(CHARIZARD));

    render(
      <CardDetailModal
        entityId="charizard"
        matched={{ tags: ["acceleration"], semantic: true }}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).toContain("matched_tags=acceleration");
    expect(url).toContain("matched_semantic=true");
  });

  it("closes on backdrop click, close button, and Escape", async () => {
    vi.mocked(fetch).mockResolvedValue(detailResponse(CHARIZARD));
    const onClose = vi.fn();
    const { container, rerender } = render(<CardDetailModal entityId="charizard" onClose={onClose} />);
    await waitFor(() => expect(screen.getByRole("heading", { name: "Charizard" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).toHaveBeenCalledTimes(1); // clicking inside the dialog itself does not close it

    fireEvent.click(container.querySelector(".modal-backdrop")!);
    expect(onClose).toHaveBeenCalledTimes(2);

    rerender(<CardDetailModal entityId="charizard" onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(3);
  });
});
