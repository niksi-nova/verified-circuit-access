"use client";

import * as ToggleGroup from "@radix-ui/react-toggle-group";
import styles from "./ModeToggle.module.css";

export type Mode = "reader" | "review";

export function ModeToggle({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <ToggleGroup.Root
      className={styles.group}
      type="single"
      value={mode}
      onValueChange={(v) => v && onChange(v as Mode)}
      aria-label="Mode"
    >
      <ToggleGroup.Item className={styles.item} value="reader">
        Reader (student)
      </ToggleGroup.Item>
      <ToggleGroup.Item className={styles.item} value="review">
        Review (teacher)
      </ToggleGroup.Item>
    </ToggleGroup.Root>
  );
}
