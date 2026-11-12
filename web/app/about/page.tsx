import styles from "./page.module.css";

export default function AboutPage() {
  return (
    <div className={styles.wrap}>
      <h1>About</h1>
      <p>
        This is a reading room for hand-drawn circuit diagrams. A program looks at a
        drawing, finds the parts and wires, and writes out a plain-language
        description of the circuit in three layers: an overview, any recognizable
        textbook blocks, and a part-by-part walkthrough.
      </p>
      <p>
        It is meant for a blind or low-vision student working through a circuits
        textbook, and for a teacher checking that student&apos;s material.
      </p>
      <h2>What &quot;machine-read&quot; means</h2>
      <p>
        Every circuit here starts out machine-read: a program produced the
        description, and nobody has checked it yet. The program also checks its own
        work with simple rules (does every terminal connect to something? are two
        terminals of the same part short-circuited together?) and a small statistical
        model trained to guess which parts are likely wrong. Both are shown as plain
        reasons, never hidden behind a single score.
      </p>
      <h2>What &quot;teacher-confirmed&quot; means</h2>
      <p>
        A teacher can read a circuit in Review mode, confirm or mark individual parts
        as wrong with a short note, and sign the whole circuit off. That sign-off is
        saved in the teacher&apos;s own browser only. Nothing here edits the
        underlying netlist — review notes are a record, not a correction.
      </p>
      <h2>What this is not</h2>
      <p>
        It has not been tested with blind students or teachers, has not been compared
        against a general-purpose vision model, and does not yet produce Braille,
        tactile diagrams, or circuit-simulator input. The <a href="/status">Status</a>{" "}
        page lists exactly what is and isn&apos;t built.
      </p>
    </div>
  );
}
