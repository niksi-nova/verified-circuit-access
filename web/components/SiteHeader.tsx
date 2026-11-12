import Link from "next/link";
import { BrailleCell, DIVIDER_PATTERN } from "@/components/BrailleCell";
import { ThemeToggle } from "@/components/ThemeToggle";
import styles from "./SiteHeader.module.css";

export function SiteHeader() {
  return (
    <header className={styles.header}>
      <Link href="/" className={styles.brand}>
        <BrailleCell pattern={DIVIDER_PATTERN} />
        Braille Press
      </Link>
      <nav className={styles.nav} aria-label="Primary">
        <Link href="/">Library</Link>
        <Link href="/status">Status</Link>
        <Link href="/about">About</Link>
      </nav>
      <div className={styles.right}>
        <ThemeToggle />
      </div>
    </header>
  );
}
