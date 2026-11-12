import Link from "next/link";
import { BrailleCell, DIVIDER_PATTERN } from "@/components/BrailleCell";
import { LibraryList, type CircuitSummary } from "@/components/LibraryList";
import { dataAvailable, getAllCircuits, START_HERE_CLEAN, START_HERE_FLAGGED } from "@/lib/data";
import styles from "./page.module.css";

export default function LibraryPage() {
  if (!dataAvailable()) {
    return (
      <div className={styles.wrap}>
        <h1>Library</h1>
        <p>
          No circuit data found at <code>public/data</code>. Run{" "}
          <code>uv run python scripts/build_demo_data.py ...</code> then{" "}
          <code>npm run sync-data</code> (or rely on the symlink).
        </p>
      </div>
    );
  }

  const circuits = getAllCircuits();
  const summaries: CircuitSummary[] = circuits.map((c) => ({
    id: c.id,
    componentCount: c.components.length,
    flaggedCount: c.flagged_count,
  }));

  return (
    <div className={styles.wrap}>
      <h1>Library</h1>
      <p className={styles.intro}>
        An index of {circuits.length} circuit diagrams, read automatically from hand-drawn
        images. Every entry is machine-read until a teacher confirms it.
      </p>

      <section className={styles.startHere} aria-label="Start here">
        <h2 className={styles.startHereTitle}>
          <BrailleCell pattern={DIVIDER_PATTERN} /> Start here
        </h2>
        <div className={styles.startHereGroup}>
          <span className="small-caps">Clean examples</span>
          <ul className={styles.startHereList}>
            {START_HERE_CLEAN.map((id) => (
              <li key={id}>
                <Link href={`/circuit/${id}`}>{id}</Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <span className="small-caps">Several parts flagged</span>
          <ul className={styles.startHereList}>
            {START_HERE_FLAGGED.map((id) => (
              <li key={id}>
                <Link href={`/circuit/${id}`}>{id}</Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <LibraryList circuits={summaries} />

      <p className={styles.notice}>
        Status filters that depend on teacher sign-off use this browser&apos;s saved
        decisions only.
      </p>
    </div>
  );
}
