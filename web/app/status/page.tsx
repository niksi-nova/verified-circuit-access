import { getStatus } from "@/lib/data";
import type { MetricsBlock } from "@/lib/types";
import styles from "./page.module.css";

const NOT_RUN = [
  "Braille (.brf) output",
  "ngspice electrical calculations",
  "Tactile SVG generation",
  "Comparison with a general-purpose vision model",
  "Evaluation on a textbook test set",
  "A comprehension evaluation with real readers",
  "Testing with blind students and teachers",
];

function MetricsTable({ title, block }: { title: string; block: MetricsBlock }) {
  if (block === "not available") {
    return (
      <section>
        <h2>{title}</h2>
        <p>not available</p>
      </section>
    );
  }
  const entries = Object.entries(block).filter(([, v]) => typeof v !== "object");
  return (
    <section>
      <h2>{title}</h2>
      <table className={styles.table}>
        <tbody>
          {entries.map(([key, value]) => (
            <tr key={key}>
              <th scope="row">{key}</th>
              <td>{String(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default function StatusPage() {
  const status = getStatus();

  return (
    <div className={styles.wrap}>
      <h1>Status</h1>
      <p>
        Every number below comes from a saved metrics file written by a real run (see{" "}
        <code>status.json</code>). Nothing here is estimated or hard-coded.
      </p>

      {!status ? (
        <p>not available — run <code>scripts/build_demo_data.py</code> first.</p>
      ) : (
        <>
          <MetricsTable title="Netlist pipeline (122 circuits)" block={status.pipeline} />
          <MetricsTable title="Error checker (verifier)" block={status.verifier} />
          <MetricsTable title="Symbol detector" block={status.detector} />
          <MetricsTable title="Wire crossing detector" block={status.crossing} />

          <div className={styles.note}>
            <p>{status.verifier_note}</p>
          </div>
        </>
      )}

      <h2>Not run</h2>
      <p>These have not been built or evaluated yet:</p>
      <ul className={styles.notRunList}>
        {NOT_RUN.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
