import { printingLabel } from "../lib/ptcgl";
import type { Printing } from "../lib/types";

// Stands in for card art when no printing of the card has any (issue #125). Pass `printing` only
// where a specific printing is meant (a deck line); an entity's tile shows the name alone.
interface CardPlaceholderProps {
  name: string;
  printing?: Pick<Printing, "set_code" | "local_id">;
}

export function CardPlaceholder({ name, printing }: CardPlaceholderProps) {
  const label = printing ? printingLabel(printing.set_code, printing.local_id) : null;
  const ariaLabel = [name, label, "(no image)"].filter(Boolean).join(" ");
  return (
    <div className="card-placeholder" role="img" aria-label={ariaLabel}>
      <span>{name}</span>
      {label && <span className="card-placeholder-printing">{label}</span>}
    </div>
  );
}
