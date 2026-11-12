"use client";

import { useState, type FormEvent } from "react";
import { api } from "@/lib/engine";
import type { Circuit } from "@/lib/types";
import styles from "./Downloads.module.css";

const UNITS: Record<string, string> = { resistor: "Ω", voltage: "V", current: "A" };
const MARKERS = new Set(["ground", "port", "vdd"]);

export interface SpiceResult {
  unit: string;
  values: Record<string, number>;
  nodes: Record<string, string>;
  deck: string;
}

export function CalculationResult({ result }: { result: SpiceResult }) {
  return (
    <section aria-label="Calculation result">
      <p>Calculated by ngspice from values entered by the teacher.</p>
      <ul>
        {Object.entries(result.values).map(([name, value]) => (
          <li key={name}>{name} = {value} {result.unit}</li>
        ))}
      </ul>
      <details>
        <summary>Generated SPICE deck and net names</summary>
        <ul>
          {Object.entries(result.nodes).map(([name, node]) => <li key={name}>{name} → {node}</li>)}
        </ul>
        <pre className={styles.deck}>{result.deck}</pre>
      </details>
    </section>
  );
}

export function Calculation({ circuit, result, onResult }: {
  circuit: Circuit;
  result?: SpiceResult;
  onResult: (result?: SpiceResult) => void;
}) {
  const [operation, setOperation] = useState("voltages");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const netlist = circuit.netlist;
  const parts = netlist?.components.filter((part) => Object.hasOwn(UNITS, part.canonical_category)) ?? [];
  const unsupported = [...new Set(netlist?.components
    .map((part) => part.canonical_category)
    .filter((name) => !Object.hasOwn(UNITS, name) && !MARKERS.has(name)))];

  async function calculate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const values = Object.fromEntries(parts.map((part) => [part.id, Number(form.get(part.id))]));
    setBusy(true);
    setError("");
    onResult(undefined);
    try {
      onResult(await api<SpiceResult>("calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          netlist, operation, values, reference: form.get("reference"), target: form.get("target"),
        }),
      }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Calculation could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className={styles.calculation}>
      <summary>Add values to calculate</summary>
      {!netlist ? <p>Not run. Reanalyse the image or rebuild the Library to include its netlist.</p>
        : unsupported.length > 0 ? <p>Not supported yet: {unsupported.join(", ")}.</p>
        : parts.length === 0 ? <p>Not supported yet. This circuit has no supported electrical parts.</p>
        : (
          <form onSubmit={calculate} onChange={() => onResult(undefined)}>
            <p>Check the circuit connections and enter values in ohms, volts or amperes.</p>
            <fieldset disabled={busy}>
              <legend>Teacher-entered values</legend>
              {parts.map((part) => (
                <label key={part.id}>{part.id} {part.canonical_category} ({UNITS[part.canonical_category]})
                  <input required type="number" step="any" name={part.id} />
                </label>
              ))}
            </fieldset>
            <fieldset disabled={busy}>
              <legend>Calculation</legend>
              <label>Operation
                <select value={operation} onChange={(event) => setOperation(event.target.value)}>
                  <option value="voltages">Node voltages</option>
                  <option value="resistance">Equivalent resistance between two nets</option>
                </select>
              </label>
              <label>Reference net
                <select name="reference" defaultValue={netlist.nets.find((net) => /^(gnd|ground)$/i.test(net.name))?.name}>
                  {netlist.nets.map((net) => <option key={net.name}>{net.name}</option>)}
                </select>
              </label>
              {operation === "resistance" && (
                <label>Test net
                  <select name="target">
                    {netlist.nets.map((net) => <option key={net.name}>{net.name}</option>)}
                  </select>
                </label>
              )}
              <button type="submit">Calculate with ngspice</button>
            </fieldset>
          </form>
        )}
      <div role="status">{busy ? "Calculating…" : result ? "Calculation complete." : ""}</div>
      {error && <p role="alert">{error}</p>}
      {result && <CalculationResult result={result} />}
    </details>
  );
}
