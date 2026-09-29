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
  sub_category: { exposed: "Sub-category" },
  retreat: { exposed: "Minimum Retreat" },
  attack_cost: { exposed: "Minimum Attack cost" },
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

describe("FilterPanel HP range", () => {
  function renderPanel(filters: Filters = {}) {
    const onFilterChange = vi.fn();
    render(<FilterPanel filters={filters} facets={{}} onFilterChange={onFilterChange} onFacetChange={vi.fn()} />);
    return onFilterChange;
  }

  it("sends only a lower bound when only the minimum is moved", () => {
    const onFilterChange = renderPanel();
    fireEvent.change(screen.getByLabelText("Minimum HP"), { target: { value: "100" } });
    expect(onFilterChange).toHaveBeenCalledWith({ hp: { gte: 100 } });
  });

  it("sends only an upper bound when only the maximum is moved", () => {
    const onFilterChange = renderPanel();
    fireEvent.change(screen.getByLabelText("Maximum HP"), { target: { value: "200" } });
    expect(onFilterChange).toHaveBeenCalledWith({ hp: { lte: 200 } });
  });

  it("keeps the other bound when one is moved", () => {
    const onFilterChange = renderPanel({ hp: { lte: 200 } });
    fireEvent.change(screen.getByLabelText("Minimum HP"), { target: { value: "100" } });
    expect(onFilterChange).toHaveBeenCalledWith({ hp: { gte: 100, lte: 200 } });
  });

  it("sends null when the minimum returns to its extreme and no maximum is set", () => {
    const onFilterChange = renderPanel({ hp: { gte: 100 } });
    fireEvent.change(screen.getByLabelText("Minimum HP"), { target: { value: "0" } });
    expect(onFilterChange).toHaveBeenCalledWith({ hp: null });
  });

  it("sends null when the maximum returns to its extreme and no minimum is set", () => {
    const onFilterChange = renderPanel({ hp: { lte: 200 } });
    fireEvent.change(screen.getByLabelText("Maximum HP"), { target: { value: "340" } });
    expect(onFilterChange).toHaveBeenCalledWith({ hp: null });
  });

  it("drops only the returned bound when the other side is still set", () => {
    const onFilterChange = renderPanel({ hp: { gte: 100, lte: 200 } });
    fireEvent.change(screen.getByLabelText("Minimum HP"), { target: { value: "0" } });
    expect(onFilterChange).toHaveBeenCalledWith({ hp: { lte: 200 } });
  });
});

describe("FilterPanel retreat and attack cost ranges", () => {
  function renderPanel(filters: Filters = {}) {
    const onFilterChange = vi.fn();
    render(<FilterPanel filters={filters} facets={{}} onFilterChange={onFilterChange} onFacetChange={vi.fn()} />);
    return onFilterChange;
  }

  it("runs retreat from 0 to 4 in steps of 1 with a 4+ top stop", () => {
    renderPanel();
    const minimum = screen.getByLabelText("Minimum Retreat");
    const maximum = screen.getByLabelText("Maximum Retreat");
    expect(minimum).toHaveAttribute("min", "0");
    expect(minimum).toHaveAttribute("max", "4");
    expect(minimum).toHaveAttribute("step", "1");
    expect(maximum).toHaveValue("4");
    expect(screen.getByText("Max 4+")).toBeInTheDocument();
  });

  it("runs attack cost from 0 to 5 in steps of 1 with a 5+ top stop and an any-attack caption", () => {
    renderPanel();
    const minimum = screen.getByLabelText("Minimum Attack cost");
    const maximum = screen.getByLabelText("Maximum Attack cost");
    expect(minimum).toHaveAttribute("min", "0");
    expect(minimum).toHaveAttribute("max", "5");
    expect(minimum).toHaveAttribute("step", "1");
    expect(maximum).toHaveValue("5");
    expect(screen.getByText("Max 5+")).toBeInTheDocument();
    expect(screen.getByText("Matches if any attack costs in this range")).toBeInTheDocument();
  });

  it("sends no upper bound when the retreat maximum sits at its top stop", () => {
    const onFilterChange = renderPanel({ retreat: { gte: 1, lte: 3 } });
    fireEvent.change(screen.getByLabelText("Maximum Retreat"), { target: { value: "4" } });
    expect(onFilterChange).toHaveBeenCalledWith({ retreat: { gte: 1 } });
  });

  it("sends null when an untouched attack-cost slider is nudged back to its extreme", () => {
    const onFilterChange = renderPanel({ attack_cost: { gte: 2 } });
    fireEvent.change(screen.getByLabelText("Minimum Attack cost"), { target: { value: "0" } });
    expect(onFilterChange).toHaveBeenCalledWith({ attack_cost: null });
  });
});

describe("FilterPanel Pokémon chip row", () => {
  function renderPanel(filters: Filters = {}) {
    const onFilterChange = vi.fn();
    render(<FilterPanel filters={filters} facets={{}} onFilterChange={onFilterChange} onFacetChange={vi.fn()} />);
    return onFilterChange;
  }

  function chip(group: string, name: string) {
    return within(screen.getByRole("group", { name: group })).getByRole("button", { name });
  }

  it("replaces the Stage dropdown with Basic, Stage 1 and Stage 2 chips", () => {
    renderPanel();
    expect(screen.queryByRole("combobox", { name: "Stage" })).not.toBeInTheDocument();
    const names = within(screen.getByRole("group", { name: "Stage" }))
      .getAllByRole("button")
      .map((button) => button.textContent);
    expect(names).toEqual(["Basic", "Stage 1", "Stage 2"]);
  });

  it("selects a stage and sets Category to Pokémon in the same edit", () => {
    const onFilterChange = renderPanel();
    fireEvent.click(chip("Stage", "Stage 1"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Pokemon", stage: "Stage 1" });
  });

  it("clears the stage when the selected chip is clicked again", () => {
    const onFilterChange = renderPanel({ category: "Pokemon", stage: "Basic" });
    fireEvent.click(chip("Stage", "Basic"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Pokemon", stage: null });
  });

  it("switches stage when another stage chip is clicked", () => {
    const onFilterChange = renderPanel({ category: "Pokemon", stage: "Basic" });
    fireEvent.click(chip("Stage", "Stage 2"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Pokemon", stage: "Stage 2" });
  });

  it("marks only the current stage chip as pressed", () => {
    renderPanel({ category: "Pokemon", stage: "Stage 1" });
    expect(chip("Stage", "Basic")).toHaveAttribute("aria-pressed", "false");
    expect(chip("Stage", "Stage 1")).toHaveAttribute("aria-pressed", "true");
    expect(chip("Stage", "Stage 2")).toHaveAttribute("aria-pressed", "false");
  });

  it("toggles ex and Mega independently and sets Category to Pokémon", () => {
    const onFilterChange = renderPanel();
    fireEvent.click(chip("Sub-category", "ex"));
    expect(onFilterChange).toHaveBeenLastCalledWith({ category: "Pokemon", sub_category: ["ex"] });
  });

  it("adds Mega alongside an already selected ex", () => {
    const onFilterChange = renderPanel({ category: "Pokemon", sub_category: ["ex"] });
    fireEvent.click(chip("Sub-category", "Mega"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Pokemon", sub_category: ["ex", "mega"] });
  });

  it("removes only the clicked sub-category, and sends null when none remain", () => {
    const both = renderPanel({ category: "Pokemon", sub_category: ["ex", "mega"] });
    fireEvent.click(chip("Sub-category", "ex"));
    expect(both).toHaveBeenCalledWith({ category: "Pokemon", sub_category: ["mega"] });
  });

  it("sends null sub_category when the last chip is switched off", () => {
    const onFilterChange = renderPanel({ category: "Pokemon", sub_category: ["mega"] });
    fireEvent.click(chip("Sub-category", "Mega"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Pokemon", sub_category: null });
  });

  it("reflects stage and sub-category set by a parsed query", () => {
    renderPanel({ category: "Pokemon", stage: "Stage 2", sub_category: ["ex", "mega"] });
    expect(chip("Stage", "Stage 2")).toHaveAttribute("aria-pressed", "true");
    expect(chip("Sub-category", "ex")).toHaveAttribute("aria-pressed", "true");
    expect(chip("Sub-category", "Mega")).toHaveAttribute("aria-pressed", "true");
  });

  it("leaves the Category dropdown in place", () => {
    renderPanel();
    expect(screen.getByRole("combobox", { name: "Category" })).toBeInTheDocument();
  });
});
