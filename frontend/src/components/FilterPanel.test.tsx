import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Facets, Filters } from "../lib/types";
import { FilterPanel } from "./FilterPanel";

// Drift guard (#48): every field of the frontend Filters/Facets shape must be classified here as
// either exposed (the panel has a control with that label) or exempt (deliberately not yet, with a
// reason). The Record types make TypeScript fail — naming the missing field — when the shape gains
// a field that isn't classified, so run `npm run typecheck` after touching lib/types.ts. When a
// panel ticket from #46 adds a control, move its field from exempt to exposed. Once #46 is done,
// exempt should be empty or carry a reason that isn't "not built yet".
type Coverage = { exposed: string } | { exempt: string };

const NOT_BUILT = "not built yet (#46)";

const FILTER_COVERAGE = {
  category: { exposed: "Category" },
  types: { exposed: "Type" },
  hp: { exposed: "Minimum HP" },
  stage: { exposed: "Stage" },
  format: { exempt: NOT_BUILT },
  sub_category: { exempt: NOT_BUILT },
  retreat: { exempt: NOT_BUILT },
  attack_cost: { exempt: NOT_BUILT },
  trainer_type: { exempt: NOT_BUILT },
  energy_type: { exempt: NOT_BUILT },
  set_id: { exempt: NOT_BUILT },
} satisfies Record<keyof Required<Filters>, Coverage>;

const FACET_COVERAGE = {
  regulation_mark: { exposed: "Regulation mark" },
  rarity: { exposed: "Rarity" },
} satisfies Record<keyof Required<Facets>, Coverage>;

describe("FilterPanel drift guard", () => {
  it("has a control for every field marked exposed", () => {
    render(<FilterPanel filters={{}} facets={{}} onFilterChange={vi.fn()} onFacetChange={vi.fn()} />);

    const coverage: Record<string, Coverage> = { ...FILTER_COVERAGE, ...FACET_COVERAGE };
    for (const [field, entry] of Object.entries(coverage)) {
      if (!("exposed" in entry)) continue;
      expect(
        screen.getAllByLabelText(entry.exposed).length,
        `field "${field}" is marked exposed but the panel has no "${entry.exposed}" control`,
      ).toBeGreaterThan(0);
    }
  });
});

describe("FilterPanel", () => {
  it("shows G, H, I and J regulation-mark chips", () => {
    render(<FilterPanel filters={{}} facets={{}} onFilterChange={vi.fn()} onFacetChange={vi.fn()} />);

    const group = screen.getByRole("group", { name: "Regulation mark" });
    const chips = within(group)
      .getAllByRole("button")
      .map((chip) => chip.textContent);
    expect(chips).toEqual(["G", "H", "I", "J"]);
  });

  it("clicking the J chip filters to J cards", () => {
    const onFacetChange = vi.fn();
    render(<FilterPanel filters={{}} facets={{}} onFilterChange={vi.fn()} onFacetChange={onFacetChange} />);

    const group = screen.getByRole("group", { name: "Regulation mark" });
    fireEvent.click(within(group).getByRole("button", { name: "J" }));

    expect(onFacetChange).toHaveBeenCalledWith({ regulation_mark: ["J"] });
  });
});
