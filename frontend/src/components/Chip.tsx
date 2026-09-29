import type { ReactNode } from "react";

interface ChipProps {
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}

export function Chip({ active, onClick, disabled, children }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={active ? "chip chip-active" : "chip"}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
