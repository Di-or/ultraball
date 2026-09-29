import {
  ATTACK_COST_MAX,
  ATTACK_COST_MIN,
  ATTACK_COST_STEP,
  CATEGORIES,
  HP_MAX,
  HP_MIN,
  HP_STEP,
  POKEMON_TYPES,
  REGULATION_MARKS,
  RARITIES,
  RETREAT_MAX,
  RETREAT_MIN,
  RETREAT_STEP,
  POKEMON_SUB_CATEGORIES,
  STAGES,
} from "../lib/constants";
import type { Category, Facets, Filters } from "../lib/types";
import { RangeControl } from "./RangeControl";

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
        <h3>Pokémon</h3>
        <div className="chip-group" role="group" aria-label="Pokémon">
          <div className="chip-group" role="group" aria-label="Stage">
            {STAGES.map((stage) => {
              const active = filters.stage === stage;
              return (
                <button
                  key={stage}
                  type="button"
                  aria-pressed={active}
                  className={active ? "chip chip-active" : "chip"}
                  onClick={() => onFilterChange({ category: "Pokemon", stage: active ? null : stage })}
                >
                  {stage}
                </button>
              );
            })}
          </div>
          <span className="chip-divider" aria-hidden="true" />
          <div className="chip-group" role="group" aria-label="Sub-category">
            {POKEMON_SUB_CATEGORIES.map(({ value, label }) => {
              const active = (filters.sub_category ?? []).includes(value);
              return (
                <button
                  key={value}
                  type="button"
                  aria-pressed={active}
                  className={active ? "chip chip-active" : "chip"}
                  onClick={() => {
                    const next = toggle(filters.sub_category, value);
                    onFilterChange({ category: "Pokemon", sub_category: next.length ? next : null });
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>
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
        <RangeControl
          label="HP"
          min={HP_MIN}
          max={HP_MAX}
          step={HP_STEP}
          value={filters.hp}
          onChange={(hp) => onFilterChange({ hp })}
        />
      </section>

      <section>
        <h3>Retreat</h3>
        <RangeControl
          label="Retreat"
          min={RETREAT_MIN}
          max={RETREAT_MAX}
          step={RETREAT_STEP}
          topLabel={`${RETREAT_MAX}+`}
          value={filters.retreat}
          onChange={(retreat) => onFilterChange({ retreat })}
        />
      </section>

      <section>
        <h3>Attack cost</h3>
        <RangeControl
          label="Attack cost"
          min={ATTACK_COST_MIN}
          max={ATTACK_COST_MAX}
          step={ATTACK_COST_STEP}
          topLabel={`${ATTACK_COST_MAX}+`}
          value={filters.attack_cost}
          onChange={(attack_cost) => onFilterChange({ attack_cost })}
        />
        <p className="filter-caption">Matches if any attack costs in this range</p>
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
