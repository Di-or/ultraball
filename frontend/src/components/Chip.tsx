import type { ReactNode } from "react";

interface ChipProps {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}

export function Chip({ active, onClick, children }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={active ? "chip chip-active" : "chip"}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
