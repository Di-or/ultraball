import { useEffect, useRef, useState, type Dispatch } from "react";
import { DeckImportRejected, getEnergyBasics, importDeck, validateDeck } from "../lib/api";
import { exportToPtcgl } from "../lib/ptcgl";
import type { Counts, EnergyBasic, Violation } from "../lib/types";
import type { DeckAction, DeckLine } from "../state/deckState";

const REQUIRED_DECK_SIZE = 60;
const VALIDATE_DEBOUNCE_MS = 400;
const SECTION_ORDER: Array<{ category: string; heading: string }> = [
  { category: "Pokemon", heading: "Pokémon" },
  { category: "Trainer", heading: "Trainer" },
  { category: "Energy", heading: "Energy" },
];

interface DeckPanelProps {
  lines: DeckLine[];
  dispatch: Dispatch<DeckAction>;
}

export function DeckPanel({ lines, dispatch }: DeckPanelProps) {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [legal, setLegal] = useState<boolean | null>(null);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [palette, setPalette] = useState<EnergyBasic[]>([]);
  const [importText, setImportText] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const [exportText, setExportText] = useState<string | null>(null);

  useEffect(() => {
    getEnergyBasics()
      .then((response) => setPalette(response.palette))
      .catch(() => setPalette([]));
  }, []);

  // Debounced, server-authoritative legality (CONTEXT.md: Deck panel) — no rules client-side.
  useEffect(() => {
    const controller = new AbortController();
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
        })
        .catch((err: unknown) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
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
          category: entry.category,
          set_code: entry.set_code,
          local_id: entry.local_id,
          energy_type: entry.energy_type,
        })),
      });
      setImportText("");
    } catch (err: unknown) {
      if (err instanceof DeckImportRejected) {
        setImportError(`Couldn't resolve: ${err.lines.join(", ")}`);
      } else {
        setImportError(err instanceof Error ? err.message : "import failed");
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
      </div>
      {violations.length > 0 && (
        <ul className="deck-violations" aria-label="Violations">
          {violations.map((violation) => (
            <li key={violation.code}>{violation.message}</li>
          ))}
        </ul>
      )}

      {SECTION_ORDER.map(({ category, heading }) => {
        const sectionLines = lines.filter((line) => line.category === category);
        if (sectionLines.length === 0) return null;
        return (
          <section key={category} className="deck-section" aria-label={`${heading} deck rows`}>
            <h3>{heading}</h3>
            <ul>
              {sectionLines.map((line) => (
                <li key={line.printing_id} className="deck-row">
                  <span className="deck-row-name">{line.name}</span>
                  <DeckStepper
                    count={line.count}
                    onChange={(count) => changeCount(line.printing_id, count)}
                  />
                </li>
              ))}
            </ul>
          </section>
        );
      })}

      <section className="energy-tray" aria-label="Basic Energy tray">
        <h3>Basic Energy</h3>
        <div className="energy-tray-items">
          {palette.map((energy) => (
            <button key={energy.printing_id} type="button" onClick={() => addEnergy(energy)}>
              {energy.name}
            </button>
          ))}
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
        {importError && <p role="alert">{importError}</p>}
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

interface DeckStepperProps {
  count: number;
  onChange: (count: number) => void;
}

function DeckStepper({ count, onChange }: DeckStepperProps) {
  const inputId = useRef(`stepper-${Math.random().toString(36).slice(2)}`);
  return (
    <div className="deck-stepper">
      <button type="button" aria-label="Decrease count" onClick={() => onChange(count - 1)}>
        −
      </button>
      <input
        id={inputId.current}
        type="number"
        aria-label="Card count"
        value={count}
        min={0}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <button type="button" aria-label="Increase count" onClick={() => onChange(count + 1)}>
        +
      </button>
    </div>
  );
}
