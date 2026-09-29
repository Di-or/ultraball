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

const FILTER_COVERAGE = {
  category: { exposed: "Category" },
  types: { exposed: "Type" },
  hp: { exposed: "Minimum HP" },
  stage: { exposed: "Stage" },
  format: { exposed: "Include non-Standard cards" },
  sub_category: { exposed: "Sub-category" },
  retreat: { exposed: "Minimum Retreat" },
  attack_cost: { exposed: "Minimum Attack cost" },
  trainer_type: { exposed: "Trainer type" },
  energy_type: { exposed: "Category" },
  set_id: { exposed: "Set" },
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

describe("FilterPanel non-Standard checkbox", () => {
  function renderPanel(filters: Filters = {}) {
    const onFilterChange = vi.fn();
    render(<FilterPanel filters={filters} facets={{}} onFilterChange={onFilterChange} onFacetChange={vi.fn()} />);
    return onFilterChange;
  }

  it("sits above the filter sections", () => {
    renderPanel();
    const checkbox = screen.getByLabelText("Include non-Standard cards");
    const firstHeading = screen.getAllByRole("heading")[0];
    expect(checkbox.compareDocumentPosition(firstHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("is unchecked when the filters are Standard-only", () => {
    renderPanel({ format: "standard" });
    expect(screen.getByLabelText("Include non-Standard cards")).not.toBeChecked();
  });

  it("is unchecked when format is unset, which the backend treats as Standard", () => {
    renderPanel({});
    expect(screen.getByLabelText("Include non-Standard cards")).not.toBeChecked();
  });

  it("is checked when a parsed query returns format null", () => {
    renderPanel({ format: null });
    expect(screen.getByLabelText("Include non-Standard cards")).toBeChecked();
  });

  it("checking it sends format null", () => {
    const onFilterChange = renderPanel({ format: "standard" });
    fireEvent.click(screen.getByLabelText("Include non-Standard cards"));
    expect(onFilterChange).toHaveBeenCalledWith({ format: null });
  });

  it("unchecking it sends format standard", () => {
    const onFilterChange = renderPanel({ format: null });
    fireEvent.click(screen.getByLabelText("Include non-Standard cards"));
    expect(onFilterChange).toHaveBeenCalledWith({ format: "standard" });
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

  it("removes only the clicked sub-category", () => {
    const onFilterChange = renderPanel({ category: "Pokemon", sub_category: ["ex", "mega"] });
    fireEvent.click(chip("Sub-category", "ex"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Pokemon", sub_category: ["mega"] });
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

});

describe("FilterPanel Trainer and Energy chips", () => {
  function renderPanel(filters: Filters = {}) {
    const onFilterChange = vi.fn();
    render(<FilterPanel filters={filters} facets={{}} onFilterChange={onFilterChange} onFacetChange={vi.fn()} />);
    return onFilterChange;
  }

  function chip(group: string, name: string) {
    return within(screen.getByRole("group", { name: group })).getByRole("button", { name });
  }

  it("shows Item, Supporter, Stadium and Tool chips", () => {
    renderPanel();
    const names = within(screen.getByRole("group", { name: "Trainer type" }))
      .getAllByRole("button")
      .map((button) => button.textContent);
    expect(names).toEqual(["Item", "Supporter", "Stadium", "Tool"]);
  });

  it("selects a trainer type and sets Category to Trainer in the same edit", () => {
    const onFilterChange = renderPanel();
    fireEvent.click(chip("Trainer type", "Supporter"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Trainer", trainer_type: "Supporter" });
  });

  it("clears the trainer type when the selected chip is clicked again", () => {
    const onFilterChange = renderPanel({ category: "Trainer", trainer_type: "Item" });
    fireEvent.click(chip("Trainer type", "Item"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Trainer", trainer_type: null });
  });

  it("switches trainer type when another chip is clicked", () => {
    const onFilterChange = renderPanel({ category: "Trainer", trainer_type: "Item" });
    fireEvent.click(chip("Trainer type", "Stadium"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Trainer", trainer_type: "Stadium" });
  });

  it("toggles ACE SPEC without touching Category", () => {
    const onFilterChange = renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "ACE SPEC" }));
    expect(onFilterChange).toHaveBeenCalledWith({ sub_category: ["ace-spec"] });
  });

  it("switches ACE SPEC off without touching Category, keeping other sub-categories", () => {
    const onFilterChange = renderPanel({ sub_category: ["ex", "ace-spec"] });
    fireEvent.click(screen.getByRole("button", { name: "ACE SPEC" }));
    expect(onFilterChange).toHaveBeenCalledWith({ sub_category: ["ex"] });
  });

  it("sends null sub_category when ACE SPEC is the last one switched off", () => {
    const onFilterChange = renderPanel({ category: "Trainer", sub_category: ["ace-spec"] });
    fireEvent.click(screen.getByRole("button", { name: "ACE SPEC" }));
    expect(onFilterChange).toHaveBeenCalledWith({ sub_category: null });
  });

  it("switches Category to Any when ACE SPEC is clicked under Pokémon", () => {
    const onFilterChange = renderPanel({ category: "Pokemon" });
    fireEvent.click(screen.getByRole("button", { name: "ACE SPEC" }));
    expect(onFilterChange).toHaveBeenCalledWith({ category: null, sub_category: ["ace-spec"] });
  });

  it("sets energy type Special and Category Energy from the Special Energy pill", () => {
    const onFilterChange = renderPanel();
    fireEvent.click(chip("Category", "Special Energy"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Energy", energy_type: "Special" });
  });

  it("goes back to Any when the lit Special Energy pill is clicked", () => {
    const onFilterChange = renderPanel({ category: "Energy", energy_type: "Special" });
    fireEvent.click(chip("Category", "Special Energy"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: null, energy_type: null });
  });

  it("offers no Basic Energy chip", () => {
    renderPanel();
    expect(screen.queryByRole("button", { name: /basic energy/i })).not.toBeInTheDocument();
  });

  it("reflects trainer type, ACE SPEC and category set by a parsed query", () => {
    renderPanel({ category: "Trainer", trainer_type: "Tool", sub_category: ["ace-spec"] });
    expect(chip("Trainer type", "Tool")).toHaveAttribute("aria-pressed", "true");
    expect(chip("Trainer type", "Item")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "ACE SPEC" })).toHaveAttribute("aria-pressed", "true");
    expect(chip("Category", "Trainer")).toHaveAttribute("aria-pressed", "true");
  });

  it("has no Category dropdown and no separate Special Energy chip", () => {
    renderPanel();
    expect(screen.queryByRole("combobox", { name: "Category" })).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Energy type" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Special Energy" })).toHaveLength(1);
  });

  it("shows Any, Pokémon, Trainer and Special Energy pills with Any lit when no category is set", () => {
    renderPanel();
    const buttons = within(screen.getByRole("group", { name: "Category" })).getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["Any", "Pokémon", "Trainer", "Special Energy"]);
    expect(chip("Category", "Any")).toHaveAttribute("aria-pressed", "true");
    expect(chip("Category", "Pokémon")).toHaveAttribute("aria-pressed", "false");
  });

  it("selects a category in one click", () => {
    const onFilterChange = renderPanel();
    fireEvent.click(chip("Category", "Trainer"));
    expect(onFilterChange).toHaveBeenCalledWith({ category: "Trainer" });
  });

  it("goes back to Any when a lit category pill is clicked, and when Any is clicked", () => {
    const onFilterChange = renderPanel({ category: "Pokemon" });
    fireEvent.click(chip("Category", "Pokémon"));
    expect(onFilterChange).toHaveBeenLastCalledWith({ category: null });
    fireEvent.click(chip("Category", "Any"));
    expect(onFilterChange).toHaveBeenLastCalledWith({ category: null });
  });

  it("lights the Special Energy pill for a parsed category Energy", () => {
    renderPanel({ category: "Energy" });
    expect(chip("Category", "Special Energy")).toHaveAttribute("aria-pressed", "true");
    expect(chip("Category", "Any")).toHaveAttribute("aria-pressed", "false");
  });
});

describe("FilterPanel set dropdown", () => {
  const sets = [
    { id: "sv1", code: "SVI", release_date: "2023-03-31" },
    { id: "base1", code: "BS", release_date: "1999-01-09" },
  ];

  it("offers Any plus every set labelled by code", () => {
    render(<FilterPanel filters={{}} facets={{}} sets={sets} onFilterChange={vi.fn()} onFacetChange={vi.fn()} />);
    const options = within(screen.getByLabelText("Set")).getAllByRole("option");
    expect(options.map((option) => option.textContent)).toEqual(["Any", "SVI", "BS"]);
  });

  it("sends the set id when a set is picked, and clears it on Any", () => {
    const onFilterChange = vi.fn();
    render(
      <FilterPanel filters={{ set_id: "sv1" }} facets={{}} sets={sets} onFilterChange={onFilterChange} onFacetChange={vi.fn()} />
    );
    const select = screen.getByLabelText("Set");
    fireEvent.change(select, { target: { value: "base1" } });
    expect(onFilterChange).toHaveBeenLastCalledWith({ set_id: "base1" });
    fireEvent.change(select, { target: { value: "" } });
    expect(onFilterChange).toHaveBeenLastCalledWith({ set_id: null });
  });

  it("shows the set a parsed query selected", () => {
    render(
      <FilterPanel filters={{ set_id: "base1" }} facets={{}} sets={sets} onFilterChange={vi.fn()} onFacetChange={vi.fn()} />
    );
    expect((screen.getByLabelText("Set") as HTMLSelectElement).value).toBe("base1");
  });
});
