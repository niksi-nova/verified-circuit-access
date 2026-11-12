"use client";

import { useEngineStatus } from "@/lib/engine";
import styles from "./SiteHeader.module.css";

export function EngineStatus() {
  const status = useEngineStatus();
  return <span className={styles.engine} role="status">Engine {status}</span>;
}
