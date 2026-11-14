import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CardPlaceholder } from "./CardPlaceholder";

describe("CardPlaceholder", () => {
  it("shows the card name in a labelled card-shaped tile", () => {
    render(<CardPlaceholder name="Mega Lucario ex" />);

    const tile = screen.getByRole("img", { name: "Mega Lucario ex (no image)" });
    expect(tile).toHaveTextContent("Mega Lucario ex");
  });

  it("adds the set code and number, PTCGL style, when a specific printing is meant", () => {
    render(<CardPlaceholder name="Pikachu" printing={{ set_code: "MEP", local_id: "032" }} />);

    const tile = screen.getByRole("img", { name: "Pikachu MEP 32 (no image)" });
    expect(tile).toHaveTextContent("Pikachu");
    expect(tile).toHaveTextContent("MEP 32");
  });

  it("shows no set line when no printing is given", () => {
    render(<CardPlaceholder name="Pikachu" />);

    expect(screen.getByRole("img")).toHaveTextContent(/^Pikachu$/);
  });
});
