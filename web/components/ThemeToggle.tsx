"use client";

import { useEffect, useState } from "react";
import { applyTheme, readStoredTheme, type Theme } from "@/lib/theme";
import styles from "./ThemeToggle.module.css";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | "system">("system");

  useEffect(() => {
    // localStorage is browser-only; sync once after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(readStoredTheme());
  }, []);

  function select(next: Theme | "system") {
    setTheme(next);
    applyTheme(next);
  }

  const options: Array<{ value: Theme | "system"; label: string }> = [
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
    { value: "system", label: "Auto" },
  ];

  return (
    <div className={styles.toggle} role="group" aria-label="Theme">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`${styles.button} ${theme === option.value ? styles.active : ""}`}
          aria-pressed={theme === option.value}
          onClick={() => select(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
