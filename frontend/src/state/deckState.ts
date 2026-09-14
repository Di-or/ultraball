// Client-side deck state (CONTEXT.md: Deck panel). Decks are ephemeral — no persistence,
// no accounts (spec Out of Scope) — so this just tracks lines in memory for the session.

import type { Category } from "../lib/types";

export interface DeckLine {
  printing_id: string;
  count: number;
  name: string;
  category: Category;
  set_code: string;
  local_id: string;
  energy_type: string | null;
}

export type DeckCardInput = Omit<DeckLine, "count">;

export interface DeckState {
  lines: DeckLine[];
}

export const initialDeckState: DeckState = { lines: [] };

export type DeckAction =
  // Add one copy of a card — from the results grid, card detail, or the basic-Energy tray.
  // Increments an existing line rather than duplicating it.
  | { type: "card-added"; card: DeckCardInput }
  // A stepper edit — sets the absolute count; zero or below removes the line. Steppers
  // never hard-block (CONTEXT.md: Deck panel; issue #31), so any count is accepted here —
  // legality is reported, never enforced, by the debounced `/decks/validate` call.
  | { type: "count-changed"; printing_id: string; count: number }
  // A successful PTCGL import replaces the whole deck (issue #28: import replaces the deck).
  | { type: "deck-replaced"; lines: DeckLine[] };

export function deckStateReducer(state: DeckState, action: DeckAction): DeckState {
  switch (action.type) {
    case "card-added": {
      const existing = state.lines.find((line) => line.printing_id === action.card.printing_id);
      if (existing) {
        return {
          lines: state.lines.map((line) =>
            line.printing_id === action.card.printing_id ? { ...line, count: line.count + 1 } : line
          ),
        };
      }
      return { lines: [...state.lines, { ...action.card, count: 1 }] };
    }
    case "count-changed": {
      if (action.count <= 0) {
        return { lines: state.lines.filter((line) => line.printing_id !== action.printing_id) };
      }
      return {
        lines: state.lines.map((line) =>
          line.printing_id === action.printing_id ? { ...line, count: action.count } : line
        ),
      };
    }
    case "deck-replaced":
      return { lines: action.lines };
  }
}
