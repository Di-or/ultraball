import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RangeControl } from "./RangeControl";

describe("RangeControl", () => {
  it("uses its own label, bounds and step", () => {
    render(<RangeControl label="Retreat" min={0} max={4} step={1} value={null} onChange={vi.fn()} />);

    const minimum = screen.getByLabelText("Minimum Retreat");
    const maximum = screen.getByLabelText("Maximum Retreat");
    expect(minimum).toHaveAttribute("min", "0");
    expect(minimum).toHaveAttribute("max", "4");
    expect(minimum).toHaveAttribute("step", "1");
    expect(maximum).toHaveValue("4");
  });

  it("omits a bound left at its extreme", () => {
    const onChange = vi.fn();
    render(<RangeControl label="Retreat" min={0} max={4} step={1} value={{ gte: 2 }} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Minimum Retreat"), { target: { value: "0" } });

    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("shows the top label at the top stop and plain numbers elsewhere", () => {
    render(
      <RangeControl label="Retreat" min={0} max={4} step={1} topLabel="4+" value={{ gte: 1 }} onChange={vi.fn()} />,
    );

    expect(screen.getByText("Min 1")).toBeInTheDocument();
    expect(screen.getByText("Max 4+")).toBeInTheDocument();
  });
});
