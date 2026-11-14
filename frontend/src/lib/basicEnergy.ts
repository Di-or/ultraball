// The eight Basic Energy types in play (CONTEXT.md: Basic-Energy tray); mirrors
// `_BASIC_ENERGY_TYPES` in app/catalog/energy.py.
export const BASIC_ENERGY_TYPES = [
  "Grass",
  "Fire",
  "Water",
  "Lightning",
  "Psychic",
  "Fighting",
  "Darkness",
  "Metal",
] as const;

export type BasicEnergyType = (typeof BASIC_ENERGY_TYPES)[number];

const BASIC_ENERGY_NAME = new RegExp(`^(?:basic )?(${BASIC_ENERGY_TYPES.join("|")}) energy$`, "i");

// The type a Basic Energy card's name names ("Fire" for `Fire Energy` or `Basic Fire Energy`), or
// `null`. TCGdex gives Basic Energy printings no `types`, so the name is the only place the type
// lives; the backend reads it the same way (`basic_energy_type_named`, app/catalog/energy.py).
export function basicEnergyTypeNamed(name: string): BasicEnergyType | null {
  const match = BASIC_ENERGY_NAME.exec(name.trim());
  if (!match) return null;
  return BASIC_ENERGY_TYPES.find((type) => type.toLowerCase() === match[1].toLowerCase()) ?? null;
}
