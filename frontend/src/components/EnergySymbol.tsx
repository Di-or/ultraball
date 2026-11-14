import type { ReactNode } from "react";
import type { BasicEnergyType } from "../lib/basicEnergy";

// Our own drawing of each Basic Energy type: a coloured disc with a plain mark (issue #148).
// TCGdex has no art for any Basic Energy printing, so this stands in for it. It is drawn by us,
// not copied from card art. Swap the drawing here to change it everywhere it is shown.

const MARK = "#fff";
const PSYCHIC = "#8e4dbf";

// Each type's disc colour and mark, on a 24×24 canvas with the disc at the centre.
const SYMBOLS: Record<BasicEnergyType, { disc: string; mark: ReactNode }> = {
  Grass: { disc: "#3f9b3a", mark: <path d="M12 5c-4 3-5 8-1 14 4-6 3-11 1-14z" fill={MARK} /> },
  Fire: { disc: "#d9442b", mark: <path d="M12 4c1 4 5 6 5 10a5 5 0 0 1-10 0c0-3 3-4 5-10z" fill={MARK} /> },
  Water: { disc: "#2f7fd1", mark: <path d="M12 4l5 9a5 5 0 1 1-10 0z" fill={MARK} /> },
  Lightning: { disc: "#e8b923", mark: <path d="M13 3l-6 11h4l-1 7 7-12h-4z" fill={MARK} /> },
  Psychic: {
    disc: PSYCHIC,
    mark: (
      <>
        <ellipse cx="12" cy="12" rx="7" ry="4" fill={MARK} />
        <circle cx="12" cy="12" r="2" fill={PSYCHIC} />
      </>
    ),
  },
  Fighting: { disc: "#b8682c", mark: <rect x="7" y="7" width="10" height="10" rx="2" fill={MARK} /> },
  Darkness: { disc: "#33363d", mark: <path d="M15 5a7 7 0 1 0 0 14 6 6 0 0 1 0-14z" fill={MARK} /> },
  Metal: { disc: "#8a949e", mark: <path d="M12 5l6 3.5v7L12 19l-6-3.5v-7z" fill={MARK} /> },
};

interface EnergySymbolProps {
  type: BasicEnergyType;
}

export function EnergySymbol({ type }: EnergySymbolProps) {
  const { disc, mark } = SYMBOLS[type];
  return (
    <svg className="energy-symbol" role="img" aria-label={`${type} Energy`} width={24} height={24} viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="11" fill={disc} />
      {mark}
    </svg>
  );
}
