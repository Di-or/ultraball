import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BASIC_ENERGY_TYPES } from "../lib/basicEnergy";
import { EnergySymbol } from "./EnergySymbol";

describe("EnergySymbol", () => {
  it.each(BASIC_ENERGY_TYPES)("renders a labelled symbol for %s", (type) => {
    render(<EnergySymbol type={type} />);

    expect(screen.getByRole("img", { name: `${type} Energy` })).toBeInTheDocument();
  });

  it("draws a different symbol for every type", () => {
    const drawings = BASIC_ENERGY_TYPES.map((type) => {
      const { container, unmount } = render(<EnergySymbol type={type} />);
      // Drop the label so only the drawing itself (colour and mark) is compared.
      const svg = container.querySelector("svg")!.cloneNode(true) as SVGElement;
      svg.removeAttribute("aria-label");
      const drawing = svg.innerHTML;
      unmount();
      return drawing;
    });

    expect(new Set(drawings).size).toBe(BASIC_ENERGY_TYPES.length);
  });
});
