"use client";

import type { Circuit } from "@/lib/types";
import styles from "./DiagramOverlay.module.css";

export function DiagramOverlay({
  circuit,
  highlightIds = [],
  onSelect,
}: {
  circuit: Circuit;
  highlightIds?: string[];
  onSelect?: (id: string) => void;
}) {
  const highlighted = new Set(highlightIds);
  const width = circuit.image_width ?? 1000;
  const height = circuit.image_height ?? 1000;

  return (
    <div className={styles.wrap}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        className={styles.image}
        src={`/data/images/${circuit.image}`}
        alt={`Original hand-drawn circuit diagram for circuit ${circuit.id}`}
        width={width}
        height={height}
      />
      <svg
        className={styles.overlay}
        viewBox={`0 0 ${width} ${height}`}
        role="group"
        aria-label="Detected component boxes"
      >
        {circuit.components
          .filter((c) => c.bbox)
          .map((c) => {
            const flagged = c.flags.level === "needs check";
            const isCurrent = highlighted.has(c.id);
            return (
              <rect
                key={c.id}
                x={c.bbox!.x}
                y={c.bbox!.y}
                width={c.bbox!.width}
                height={c.bbox!.height}
                className={`${styles.box} ${flagged ? styles.flagged : ""} ${
                  isCurrent ? styles.current : ""
                }`}
                role={onSelect ? "button" : undefined}
                tabIndex={onSelect ? 0 : undefined}
                aria-label={onSelect ? `${c.id}, ${c.category}` : undefined}
                onClick={onSelect ? () => onSelect(c.id) : undefined}
                onKeyDown={
                  onSelect
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelect(c.id);
                        }
                      }
                    : undefined
                }
              >
                <title>{`${c.id} — ${c.category}`}</title>
              </rect>
            );
          })}
      </svg>
    </div>
  );
}
