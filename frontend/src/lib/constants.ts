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

// mega ⊂ ex in the data (CONTEXT.md: sub_category), so selecting ex also finds Mega ex cards.
export const POKEMON_SUB_CATEGORIES = [
  { value: "ex", label: "ex" },
  { value: "mega", label: "Mega" },
] as const;

export const TRAINER_TYPES = ["Item", "Supporter", "Stadium", "Tool"] as const;

export const REGULATION_MARKS = ["G", "H", "I", "J"] as const;

export const HP_MIN = 0;
export const HP_MAX = 340;
export const HP_STEP = 10;

export const RETREAT_MIN = 0;
export const RETREAT_MAX = 4;
export const RETREAT_STEP = 1;

export const ATTACK_COST_MIN = 0;
export const ATTACK_COST_MAX = 5;
export const ATTACK_COST_STEP = 1;

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
