import {
  CATEGORIES,
  HP_MAX,
  HP_MIN,
  HP_STEP,
  POKEMON_TYPES,
  REGULATION_MARKS,
  RARITIES,
  STAGES,
} from "../lib/constants";
import type { Category, Facets, Filters, Stage } from "../lib/types";

interface FilterPanelProps {
  filters: Filters;
  facets: Facets;
  onFilterChange: (patch: Partial<Filters>) => void;
  onFacetChange: (patch: Partial<Facets>) => void;
}

function toggle<T>(list: T[] | null | undefined, value: T): T[] {
  const current = list ?? [];
  return current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
}

export function FilterPanel({ filters, facets, onFilterChange, onFacetChange }: FilterPanelProps) {
  return (
    <aside className="filter-panel" aria-label="Filters">
      <section>
        <h3>Category</h3>
        <select
          aria-label="Category"
          value={filters.category ?? ""}
          onChange={(event) =>
            onFilterChange({ category: (event.target.value || null) as Category | null })
          }
        >
          <option value="">Any</option>
          {CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </select>
      </section>

      <section>
        <h3>Stage</h3>
        <select
          aria-label="Stage"
          value={filters.stage ?? ""}
          onChange={(event) => onFilterChange({ stage: (event.target.value || null) as Stage | null })}
        >
          <option value="">Any</option>
          {STAGES.map((stage) => (
            <option key={stage} value={stage}>
              {stage}
            </option>
          ))}
        </select>
      </section>

      <section>
        <h3>Type</h3>
        <div className="chip-group" role="group" aria-label="Type">
          {POKEMON_TYPES.map((type) => {
            const active = (filters.types ?? []).includes(type);
            return (
              <button
                key={type}
                type="button"
                aria-pressed={active}
                className={active ? "chip chip-active" : "chip"}
                onClick={() => onFilterChange({ types: toggle(filters.types, type) })}
              >
                {type}
              </button>
            );
          })}
        </div>
      </section>

      <section>
        <h3>HP</h3>
        <div className="range-inputs">
          <label>
            Min {filters.hp?.gte ?? HP_MIN}
            <input
              type="range"
              aria-label="Minimum HP"
              min={HP_MIN}
              max={HP_MAX}
              step={HP_STEP}
              value={filters.hp?.gte ?? HP_MIN}
              onChange={(event) =>
                onFilterChange({ hp: { ...filters.hp, gte: Number(event.target.value) } })
              }
            />
          </label>
          <label>
            Max {filters.hp?.lte ?? HP_MAX}
            <input
              type="range"
              aria-label="Maximum HP"
              min={HP_MIN}
              max={HP_MAX}
              step={HP_STEP}
              value={filters.hp?.lte ?? HP_MAX}
              onChange={(event) =>
                onFilterChange({ hp: { ...filters.hp, lte: Number(event.target.value) } })
              }
            />
          </label>
        </div>
      </section>

      <section>
        <h3>Regulation mark</h3>
        <div className="chip-group" role="group" aria-label="Regulation mark">
          {REGULATION_MARKS.map((mark) => {
            const active = (facets.regulation_mark ?? []).includes(mark);
            return (
              <button
                key={mark}
                type="button"
                aria-pressed={active}
                className={active ? "chip chip-active" : "chip"}
                onClick={() =>
                  onFacetChange({ regulation_mark: toggle(facets.regulation_mark, mark) })
                }
              >
                {mark}
              </button>
            );
          })}
        </div>
      </section>

      <section>
        <h3>Rarity</h3>
        <div className="chip-group" role="group" aria-label="Rarity">
          {RARITIES.map((rarity) => {
            const active = (facets.rarity ?? []).includes(rarity);
            return (
              <button
                key={rarity}
                type="button"
                aria-pressed={active}
                className={active ? "chip chip-active" : "chip"}
                onClick={() => onFacetChange({ rarity: toggle(facets.rarity, rarity) })}
              >
                {rarity}
              </button>
            );
          })}
        </div>
      </section>
    </aside>
  );
}
