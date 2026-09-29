import type { IntRange } from "../lib/types";

interface RangeControlProps {
  label: string;
  min: number;
  max: number;
  step: number;
  value: IntRange | null | undefined;
  onChange: (value: IntRange | null) => void;
}

// A bound left at its extreme is omitted, and a range with neither bound is null, so an untouched
// slider never filters (a numeric bound would exclude cards that lack the field entirely).
function normalize(range: IntRange, min: number, max: number): IntRange | null {
  const next: IntRange = {};
  if (range.gte !== undefined && range.gte > min) next.gte = range.gte;
  if (range.lte !== undefined && range.lte < max) next.lte = range.lte;
  return next.gte === undefined && next.lte === undefined ? null : next;
}

export function RangeControl({ label, min, max, step, value, onChange }: RangeControlProps) {
  return (
    <div className="range-inputs">
      <label>
        Min {value?.gte ?? min}
        <input
          type="range"
          aria-label={`Minimum ${label}`}
          min={min}
          max={max}
          step={step}
          value={value?.gte ?? min}
          onChange={(event) => onChange(normalize({ ...value, gte: Number(event.target.value) }, min, max))}
        />
      </label>
      <label>
        Max {value?.lte ?? max}
        <input
          type="range"
          aria-label={`Maximum ${label}`}
          min={min}
          max={max}
          step={step}
          value={value?.lte ?? max}
          onChange={(event) => onChange(normalize({ ...value, lte: Number(event.target.value) }, min, max))}
        />
      </label>
    </div>
  );
}
