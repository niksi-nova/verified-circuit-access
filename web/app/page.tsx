import Link from "next/link";
import styles from "./page.module.css";

export default function HomePage() {
  return (
    <div className={styles.wrap}>
      <h1>Read a circuit diagram</h1>
      <p className={styles.intro}>
        Braille Press turns circuit images into plain-language explanations for blind
        and low-vision students, with a review view for teachers.
      </p>
      <Link className={styles.primary} href="/try">Try it</Link>

      <section className={styles.startHere} aria-labelledby="how-it-works">
        <h2 id="how-it-works">How it works</h2>
        <ol className={styles.steps}>
          <li>Add a circuit image.</li>
          <li>The machine reads the parts and their connections.</li>
          <li>A teacher checks the reading and can sign off.</li>
          <li>
            The student reads, hears or feels it. Text and read-aloud are available.
            Braille and raised diagram are <strong>not run</strong>.
          </li>
        </ol>
      </section>
    </div>
  );
}
