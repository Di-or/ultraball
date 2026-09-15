import { useEffect, useState } from "react";
import { getCardDetail } from "../lib/api";
import type { CardDetail, Matched } from "../lib/types";
import { MatchedChips } from "./MatchedChips";

interface CardDetailModalProps {
  entityId: string;
  matched?: Matched | null;
  onClose: () => void;
}

// Opens as an overlay on top of the still-mounted results grid (docs/archive/mvp-spec.md
// §12.4, cited by app/catalog/detail_models.py), so the grid's scroll position is untouched
// by construction — nothing navigates away.
export function CardDetailModal({ entityId, matched, onClose }: CardDetailModalProps) {
  const [detail, setDetail] = useState<CardDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setDetail(null);
    setError(null);

    getCardDetail(entityId, matched, controller.signal)
      .then(setDetail)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "failed to load card");
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityId]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={detail ? detail.name : "Card detail"}
        onClick={(event) => event.stopPropagation()}
      >
        <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
          ×
        </button>

        {error && <p role="alert">{error}</p>}
        {!error && !detail && <p aria-live="polite">Loading…</p>}

        {detail && (
          <>
            <div className="modal-header">
              {detail.image && <img src={`${detail.image}/high.webp`} alt={detail.name} className="modal-image" />}
              <div>
                <h2>{detail.name}</h2>
                <p className="card-meta">
                  {detail.category}
                  {detail.stage ? ` · ${detail.stage}` : ""}
                  {detail.hp != null ? ` · ${detail.hp} HP` : ""}
                </p>
                {detail.types.length > 0 && <p className="card-types">{detail.types.join(", ")}</p>}
                <MatchedChips matched={detail.matched} />
              </div>
            </div>

            {detail.abilities.length > 0 && (
              <section>
                <h3>Abilities</h3>
                {detail.abilities.map((ability, index) => (
                  <div key={index} className="ability">
                    <strong>{ability.name}</strong>
                    {ability.effect && <p>{ability.effect}</p>}
                  </div>
                ))}
              </section>
            )}

            {detail.attacks.length > 0 && (
              <section>
                <h3>Attacks</h3>
                {detail.attacks.map((attack, index) => (
                  <div key={index} className="attack">
                    <strong>
                      {attack.name}
                      {attack.damage != null ? ` — ${attack.damage}` : ""}
                    </strong>
                    {attack.cost && <p className="card-types">{attack.cost.join(", ")}</p>}
                    {attack.effect && <p>{attack.effect}</p>}
                  </div>
                ))}
              </section>
            )}

            {detail.tags.length > 0 && (
              <section>
                <h3>Tags</h3>
                <div className="chip-group">
                  {detail.tags.map((tag) => (
                    <span key={tag} className="chip">
                      {tag}
                    </span>
                  ))}
                </div>
              </section>
            )}

            <section>
              <h3>Printings</h3>
              <ul className="printings-list">
                {detail.printings.map((printing) => (
                  <li key={printing.printing_id}>
                    {printing.set_id}
                    {printing.rarity ? ` · ${printing.rarity}` : ""}
                    {printing.regulation_mark ? ` · Mark ${printing.regulation_mark}` : ""}
                    {!printing.is_standard_legal && <span className="illegal-flag"> · not Standard-legal</span>}
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
