import { describe, expect, it } from "vitest";
import { BASIC_ENERGY_TYPES, basicEnergyTypeNamed } from "./basicEnergy";

describe("basicEnergyTypeNamed", () => {
  it.each(BASIC_ENERGY_TYPES)("reads %s from its Basic Energy card name", (type) => {
    expect(basicEnergyTypeNamed(`${type} Energy`)).toBe(type);
  });

  it("reads the type from the Basic prefix TCGdex gives some printings", () => {
    expect(basicEnergyTypeNamed("Basic Lightning Energy")).toBe("Lightning");
  });

  it("names no type for other Energy", () => {
    expect(basicEnergyTypeNamed("Fairy Energy")).toBeNull();
    expect(basicEnergyTypeNamed("Mist Energy")).toBeNull();
    expect(basicEnergyTypeNamed("Fire Energy Plus")).toBeNull();
  });
});
