// UI-side option lists. The backend leaves `types`/`regulation_mark`/`rarity` as free-form
// strings (app/search/models.py), so these are presentation constants, not a contract.

export const POKEMON_TYPES = [
  "Grass",
  "Fire",
  "Water",
  "Lightning",
  "Psychic",
  "Fighting",
  "Darkness",
  "Metal",
  "Fairy",
  "Dragon",
  "Colorless",
] as const;

export const STAGES = ["Basic", "Stage 1", "Stage 2"] as const;

export const CATEGORIES = ["Pokemon", "Trainer", "Energy"] as const;

export const REGULATION_MARKS = ["G", "H", "I"] as const;

export const RARITIES = [
  "Common",
  "Uncommon",
  "Rare",
  "Double Rare",
  "Ultra Rare",
  "Illustration Rare",
  "Special Illustration Rare",
  "Hyper Rare",
] as const;
