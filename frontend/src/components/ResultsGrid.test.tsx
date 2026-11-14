import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResultsGrid } from "./ResultsGrid";
import type { SearchResult } from "../lib/types";

const CHARIZARD: SearchResult = {
  printing_id: "swsh4-1",
  name: "Charizard",
  category: "Pokemon",
  hp: 170,
  types: ["Fire"],
  stage: "Stage 2",
  sub_category: [],
  regulation_mark: "F",
  rarity: "Rare Holo",
  set_id: "swsh4",
  set_code: "VIV",
  local_id: "025",
  is_standard_legal: false,
  image: "https://assets.tcgdex.net/en/swsh/swsh4/25/low.webp",
  matched: null,
};

function renderGrid(results: SearchResult[]) {
  render(
    <ResultsGrid
      results={results}
      total={results.length}
      loading={false}
      error={null}
      onSelectCard={() => {}}
      onAddToDeck={() => {}}
    />,
  );
}

describe("ResultsGrid", () => {
  it("shows a tile's card art with the card name as alt text", () => {
    renderGrid([CHARIZARD]);

    expect(screen.getByRole("img", { name: "Charizard" })).toHaveAttribute(
      "src",
      "https://assets.tcgdex.net/en/swsh/swsh4/25/low.webp",
    );
  });

  it("shows a placeholder with the card name, and no set line, when no printing has art", () => {
    renderGrid([{ ...CHARIZARD, image: null }]);

    // A tile is the whole card (all its printings), so no one set code and number is meant.
    expect(screen.getByRole("img", { name: "Charizard (no image)" })).toHaveTextContent(/^Charizard$/);
    expect(screen.queryByRole("img", { name: "Charizard" })).not.toBeInTheDocument();
  });
});
