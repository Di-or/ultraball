import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FilterPanel } from "./FilterPanel";

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
