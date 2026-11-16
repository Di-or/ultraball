import { useEffect, useState, type Dispatch } from "react";
import { DeckImportRejected, getEnergyBasics, importDeck, validateDeck } from "../lib/api";
import { DECK_CATEGORY_ORDER } from "../lib/deckCategories";
import { exportToPtcgl, printingLabel } from "../lib/ptcgl";
import type { Category, Counts, EnergyBasic, Violation } from "../lib/types";
import { basicEnergyTypeNamed } from "../lib/basicEnergy";
import { CardPlaceholder } from "./CardPlaceholder";
import { EnergySymbol } from "./EnergySymbol";
import type { DeckAction, DeckLine } from "../state/deckState";

const REQUIRED_DECK_SIZE = 60;
const VALIDATE_DEBOUNCE_MS = 400;
const SECTION_HEADINGS: Record<Category, string> = {
  Pokemon: "Pokémon",
  Trainer: "Trainer",
  Energy: "Energy",
};

interface DeckPanelProps {
  lines: DeckLine[];
  dispatch: Dispatch<DeckAction>;
}

export function DeckPanel({ lines, dispatch }: DeckPanelProps) {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [legal, setLegal] = useState<boolean | null>(null);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [validating, setValidating] = useState(false);
  const [palette, setPalette] = useState<EnergyBasic[]>([]);
  const [importText, setImportText] = useState("");
  const [importError, setImportError] = useState<string[] | null>(null);
  const [exportText, setExportText] = useState<string | null>(null);

  useEffect(() => {
    getEnergyBasics()
      .then((response) => setPalette(response.palette))
      .catch(() => setPalette([]));
  }, []);

  // Debounced, server-authoritative legality (CONTEXT.md: Deck panel) — no rules client-side.
  useEffect(() => {
    const controller = new AbortController();
    setValidating(true);
    const timer = setTimeout(() => {
      validateDeck(
        {
          entries: lines.map((line) => ({ printing_id: line.printing_id, count: line.count })),
          format: "standard",
        },
        controller.signal
      )
        .then((report) => {
          setCounts(report.counts);
          setLegal(report.legal);
          setViolations(report.violations);
          setValidating(false);
        })
        .catch((err: unknown) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
          setValidating(false);
        });
    }, VALIDATE_DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [lines]);

  function addEnergy(energy: EnergyBasic) {
    dispatch({
      type: "card-added",
      card: {
        printing_id: energy.printing_id,
        name: energy.name,
        category: "Energy",
        set_code: energy.set_code,
        local_id: energy.local_id,
        energy_type: energy.energy_type,
        image: energy.image,
      },
    });
  }

  function changeCount(printing_id: string, count: number) {
    dispatch({ type: "count-changed", printing_id, count });
  }

  async function handleImport() {
    setImportError(null);
    try {
      const response = await importDeck(importText);
      dispatch({
        type: "deck-replaced",
        lines: response.entries.map((entry) => ({
          printing_id: entry.printing_id,
          count: entry.count,
          name: entry.name,
          // The backend serves `category` as a plain string (app/catalog/deck_models.py);
          // resolved import entries are always one of the three deck categories.
          category: entry.category as Category,
          set_code: entry.set_code,
          local_id: entry.local_id,
          energy_type: entry.energy_type,
          image: entry.image,
        })),
      });
      setImportText("");
    } catch (err: unknown) {
      if (err instanceof DeckImportRejected) {
        setImportError(err.lines);
      } else {
        setImportError([err instanceof Error ? err.message : "import failed"]);
      }
    }
  }

  function handleExport() {
    setExportText(exportToPtcgl(lines));
  }

  return (
    <aside className="deck-panel" aria-label="Deck">
      <h2>Deck</h2>
      <div className="deck-readout" aria-label="Deck readout">
        <span className="deck-count">{counts?.total ?? 0}/{REQUIRED_DECK_SIZE}</span>
        <span className="deck-pte">
          P {counts?.pokemon ?? 0} · T {counts?.trainer ?? 0} · E {counts?.energy ?? 0}
        </span>
        {legal != null && (
          <span
            className={`legality-light ${legal ? "legal" : "illegal"}`}
            aria-label={legal ? "Legal" : "Not legal"}
          >
            {legal ? "Legal" : "Not legal"}
          </span>
        )}
        {validating && <span aria-live="polite">Checking…</span>}
      </div>
      {violations.length > 0 && (
        <ul className="deck-violations" aria-label="Violations">
          {violations.map((violation) => (
            <li key={violation.code}>
              {violation.message}
              {violation.cards.length > 0 && ` (${violation.cards.join(", ")})`}
            </li>
          ))}
        </ul>
      )}

      {DECK_CATEGORY_ORDER.map((category) => {
        const sectionLines = lines.filter((line) => line.category === category);
        if (sectionLines.length === 0) return null;
        const heading = SECTION_HEADINGS[category];
        return (
          <section key={category} className="deck-section" aria-label={`${heading} deck cards`}>
            <h3>{heading}</h3>
            <ul className="deck-grid">
              {sectionLines.map((line) => (
                <DeckTile
                  key={line.printing_id}
                  line={line}
                  onChange={(count) => changeCount(line.printing_id, count)}
                />
              ))}
            </ul>
          </section>
        );
      })}

      <section className="energy-tray" aria-label="Basic Energy tray">
        <h3>Basic Energy</h3>
        <div className="energy-tray-items">
          {palette.map((energy) => {
            const type = basicEnergyTypeNamed(energy.name);
            return (
              <button
                key={energy.printing_id}
                type="button"
                className="energy-tray-button"
                aria-label={type ? `${type} Energy` : energy.name}
                onClick={() => addEnergy(energy)}
              >
                {type ? (
                  <>
                    <EnergySymbol type={type} />
                    {type}
                  </>
                ) : (
                  energy.name
                )}
              </button>
            );
          })}
        </div>
      </section>

      <section className="deck-import" aria-label="Import deck">
        <h3>Import</h3>
        <textarea
          aria-label="PTCGL decklist"
          value={importText}
          onChange={(event) => setImportText(event.target.value)}
        />
        <button type="button" onClick={handleImport} disabled={!importText.trim()}>
          Import
        </button>
        {importError && (
          <ul role="alert" className="import-error">
            {importError.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="deck-export" aria-label="Export deck">
        <h3>Export</h3>
        <button type="button" onClick={handleExport} disabled={lines.length === 0}>
          Export to PTCGL
        </button>
        {exportText != null && (
          <textarea aria-label="PTCGL export" value={exportText} readOnly />
        )}
      </section>
    </aside>
  );
}

interface DeckTileProps {
  line: DeckLine;
  onChange: (count: number) => void;
}

// One deck line, one exact printing (issue #149). The art is whatever the backend resolved for
// the line; the set code and number underneath say which printing it is even when that art is
// borrowed from another one. Basic Energy has no art anywhere, so it shows its symbol (#148).
// The steppers never block a count (CONTEXT.md: Deck panel): legality is only reported.
function DeckTile({ line, onChange }: DeckTileProps) {
  const label = printingLabel(line.set_code, line.local_id);
  // By name, as the tray and the backend read it: TCGdex's `energy_type` labels Special Energy
  // "Basic" too (CONTEXT.md: Basic Energy exception).
  const energyType = line.category === "Energy" ? basicEnergyTypeNamed(line.name) : null;
  const title = `${line.name} ${label}`;

  let art;
  if (energyType) {
    art = (
      <div className="deck-tile-energy">
        <EnergySymbol type={energyType} />
      </div>
    );
  } else if (line.image) {
    art = <img src={line.image} alt={title} className="deck-tile-image" loading="lazy" />;
  } else {
    art = <CardPlaceholder name={line.name} printing={line} />;
  }

  return (
    <li className="deck-tile" title={title}>
      <div className="deck-tile-art">
        {art}
        <span className="deck-tile-count" aria-label={`${line.count} ${line.count === 1 ? "copy" : "copies"}`}>
          ×{line.count}
        </span>
      </div>
      <div className="deck-tile-printing">{label}</div>
      <div className="deck-tile-stepper">
        <button type="button" aria-label={`Remove one ${title}`} onClick={() => onChange(line.count - 1)}>
          −
        </button>
        <button type="button" aria-label={`Add one ${title}`} onClick={() => onChange(line.count + 1)}>
          +
        </button>
      </div>
    </li>
  );
}
