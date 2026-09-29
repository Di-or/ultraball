import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Facets, Filters } from "../lib/types";
import { FilterPanel } from "./FilterPanel";

// Drift guard (#48): every field of the frontend Filters/Facets shape must be listed here as
// either "exposed" (the panel has a control for it) or "exempt" (deliberately not yet). The
// Record types make TypeScript fail — naming the missing field — when the shape gains a field
// that isn't classified, so run `npm run typecheck` after touching lib/types.ts. When a panel
// ticket from #46 adds a control, move its field from "exempt" to "exposed". Once #46 is done,
// "exempt" should be empty or carry a written reason.
type Coverage = "exposed" | "exempt";

const FILTER_COVERAGE = {
  category: "exposed",
  types: "exposed",
  hp: "exposed",
  stage: "exposed",
  format: "exempt",
  sub_category: "exempt",
  retreat: "exempt",
  attack_cost: "exempt",
  trainer_type: "exempt",
  energy_type: "exempt",
  set_id: "exempt",
} satisfies Record<keyof Required<Filters>, Coverage>;

const FACET_COVERAGE = {
  regulation_mark: "exposed",
  rarity: "exposed",
} satisfies Record<keyof Required<Facets>, Coverage>;

// The label of the control that carries each exposed field.
const CONTROL_LABEL: Record<string, string> = {
  category: "Category",
  types: "Type",
  hp: "Minimum HP",
  stage: "Stage",
  regulation_mark: "Regulation mark",
  rarity: "Rarity",
};

function fieldsWith(coverage: Record<string, Coverage>, value: Coverage): string[] {
  return Object.keys(coverage).filter((field) => coverage[field] === value);
}

describe("FilterPanel drift guard", () => {
  it("has a control for every field marked exposed", () => {
    render(<FilterPanel filters={{}} facets={{}} onFilterChange={vi.fn()} onFacetChange={vi.fn()} />);

    const exposed = [...fieldsWith(FILTER_COVERAGE, "exposed"), ...fieldsWith(FACET_COVERAGE, "exposed")];
    for (const field of exposed) {
      const label = CONTROL_LABEL[field];
      expect(label, `no control label recorded for exposed field "${field}"`).toBeDefined();
      expect(
        screen.queryAllByLabelText(label).length,
        `field "${field}" is marked exposed but the panel has no "${label}" control`,
      ).toBeGreaterThan(0);
    }
  });

  it("never lists a field as both exposed and exempt", () => {
    const fields = [...Object.keys(FILTER_COVERAGE), ...Object.keys(FACET_COVERAGE)];
    expect(new Set(fields).size).toBe(fields.length);
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
