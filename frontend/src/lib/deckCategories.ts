import type { Category } from "./types";

// The fixed P/T/E grouping order shared by the deck panel and PTCGL export
// (CONTEXT.md: Deck panel — "grouped Pokémon / Trainer / Energy rows").
export const DECK_CATEGORY_ORDER: Category[] = ["Pokemon", "Trainer", "Energy"];
