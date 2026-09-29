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
  TRAINER_TYPES,
} from "../lib/constants";
import type { Category, Facets, Filters, SetSummary } from "../lib/types";
import { Chip } from "./Chip";
import { RangeControl } from "./RangeControl";

interface FilterPanelProps {
  filters: Filters;
  facets: Facets;
  sets?: SetSummary[];
  onFilterChange: (patch: Partial<Filters>) => void;
  onFacetChange: (patch: Partial<Facets>) => void;
}

function toggle<T>(list: T[] | null | undefined, value: T): T[] {
  const current = list ?? [];
  return current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
}

export function FilterPanel({ filters, facets, sets = [], onFilterChange, onFacetChange }: FilterPanelProps) {
  const aceSpecActive = (filters.sub_category ?? []).includes("ace-spec");
  const specialEnergyActive = filters.energy_type === "Special";

  return (
    <aside className="filter-panel" aria-label="Filters">
      <label className="format-toggle">
        <input
          type="checkbox"
          checked={filters.format === null}
          onChange={(event) => onFilterChange({ format: event.target.checked ? null : "standard" })}
        />
        Include non-Standard cards
      </label>

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
                <Chip
                  key={stage}
                  active={active}
                  onClick={() => onFilterChange({ category: "Pokemon", stage: active ? null : stage })}
                >
                  {stage}
                </Chip>
              );
            })}
          </div>
          <span className="chip-divider" aria-hidden="true" />
          <div className="chip-group" role="group" aria-label="Sub-category">
            {POKEMON_SUB_CATEGORIES.map(({ value, label }) => {
              const active = (filters.sub_category ?? []).includes(value);
              return (
                <Chip
                  key={value}
                  active={active}
                  onClick={() => {
                    const next = toggle(filters.sub_category, value);
                    onFilterChange({ category: "Pokemon", sub_category: next.length ? next : null });
                  }}
                >
                  {label}
                </Chip>
              );
            })}
          </div>
        </div>
      </section>

      <section>
        <h3>Trainer</h3>
        <div className="chip-group" role="group" aria-label="Trainer">
          <div className="chip-group" role="group" aria-label="Trainer type">
            {TRAINER_TYPES.map((trainerType) => {
              const active = filters.trainer_type === trainerType;
              return (
                <Chip
                  key={trainerType}
                  active={active}
                  onClick={() =>
                    onFilterChange({ category: "Trainer", trainer_type: active ? null : trainerType })
                  }
                >
                  {trainerType}
                </Chip>
              );
            })}
          </div>
          <span className="chip-divider" aria-hidden="true" />
          {/* ACE SPEC leaves Category alone (its cards include Special Energy), except under
              Pokémon, where no card is ACE SPEC: there it moves Category to Any. */}
          <div className="chip-group" role="group" aria-label="Trainer sub-category">
            <Chip
              active={aceSpecActive}
              onClick={() => {
                const next = toggle(filters.sub_category, "ace-spec" as const);
                const sub_category = next.length ? next : null;
                onFilterChange(filters.category === "Pokemon" ? { category: null, sub_category } : { sub_category });
              }}
            >
              ACE SPEC
            </Chip>
          </div>
        </div>
      </section>

      <section>
        <h3>Energy</h3>
        <div className="chip-group" role="group" aria-label="Energy type">
          <Chip
            active={specialEnergyActive}
            onClick={() =>
              onFilterChange({ category: "Energy", energy_type: specialEnergyActive ? null : "Special" })
            }
          >
            Special Energy
          </Chip>
        </div>
      </section>

      <section>
        <h3>Type</h3>
        <div className="chip-group" role="group" aria-label="Type">
          {POKEMON_TYPES.map((type) => {
            const active = (filters.types ?? []).includes(type);
            return (
              <Chip
                key={type}
                active={active}
                onClick={() => onFilterChange({ types: toggle(filters.types, type) })}
              >
                {type}
              </Chip>
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
        <h3>Set</h3>
        <select
          aria-label="Set"
          value={filters.set_id ?? ""}
          onChange={(event) => onFilterChange({ set_id: event.target.value || null })}
        >
          <option value="">Any</option>
          {sets.map((set) => (
            <option key={set.id} value={set.id}>
              {set.code}
            </option>
          ))}
        </select>
      </section>

      <section>
        <h3>Regulation mark</h3>
        <div className="chip-group" role="group" aria-label="Regulation mark">
          {REGULATION_MARKS.map((mark) => {
            const active = (facets.regulation_mark ?? []).includes(mark);
            return (
              <Chip
                key={mark}
                active={active}
                onClick={() =>
                  onFacetChange({ regulation_mark: toggle(facets.regulation_mark, mark) })
                }
              >
                {mark}
              </Chip>
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
              <Chip
                key={rarity}
                active={active}
                onClick={() => onFacetChange({ rarity: toggle(facets.rarity, rarity) })}
              >
                {rarity}
              </Chip>
            );
          })}
        </div>
      </section>
    </aside>
  );
}
