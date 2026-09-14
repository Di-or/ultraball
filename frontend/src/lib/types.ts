// Mirrors app/search/models.py — keep in sync with the backend's Filters/Facets/SearchResponse.

export interface IntRange {
  gte?: number;
  lte?: number;
}

export type Category = "Pokemon" | "Trainer" | "Energy";
export type SubCategory = "ex" | "mega" | "ace-spec";
export type Stage = "Basic" | "Stage 1" | "Stage 2";
export type TrainerType = "Item" | "Supporter" | "Stadium" | "Tool";

export interface Filters {
  format?: "standard" | null;
  category?: Category | null;
  sub_category?: SubCategory[] | null;
  types?: string[] | null;
  hp?: IntRange | null;
  retreat?: IntRange | null;
  attack_cost?: IntRange | null;
  stage?: Stage | null;
  trainer_type?: TrainerType | null;
  energy_type?: string | null;
  set_id?: string | null;
}

export interface Facets {
  regulation_mark?: string[] | null;
  rarity?: string[] | null;
}

export interface SearchRequest {
  query?: string | null;
  filters: Filters;
  facets: Facets;
  limit: number;
  offset: number;
}

export interface Matched {
  tags: string[];
  semantic: boolean;
}

export interface SearchResult {
  entity_id: string;
  printing_id: string;
  name: string;
  category: string;
  hp: number | null;
  types: string[];
  stage: string | null;
  sub_category: string[];
  regulation_mark: string | null;
  rarity: string | null;
  set_id: string;
  is_standard_legal: boolean;
  matched: Matched | null;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  limit: number;
  offset: number;
  filters: Filters;
}

export const EMPTY_FILTERS: Filters = { format: "standard" };
export const EMPTY_FACETS: Facets = {};

// Mirrors app/catalog/detail_models.py — GET /cards/{entity_id}.

export interface Attack {
  name: string;
  cost?: string[];
  damage?: number | string;
  effect?: string;
}

export interface Ability {
  name: string;
  type?: string;
  effect?: string;
}

export interface Printing {
  printing_id: string;
  set_id: string;
  regulation_mark: string | null;
  rarity: string | null;
  image: string | null;
  is_standard_legal: boolean;
}

export interface CardDetail {
  entity_id: string;
  printing_id: string;
  name: string;
  category: string;
  hp: number | null;
  types: string[];
  stage: string | null;
  evolve_from: string | null;
  retreat: number | null;
  regulation_mark: string | null;
  rarity: string | null;
  set_id: string;
  sub_category: string[];
  trainer_type: string | null;
  energy_type: string | null;
  attacks: Attack[];
  abilities: Ability[];
  attack_costs: number[];
  image: string | null;
  is_standard_legal: boolean;
  tags: string[];
  printings: Printing[];
  matched: Matched | null;
}
