import styles from "./BrailleCell.module.css";

/** A 2x3 Braille cell, dots numbered 1,4 / 2,5 / 3,6 (top to bottom,
 * left column then right). Used as a divider (all dots), a bullet (dot
 * 1 only) or a loading mark (cycling). Decorative by default
 * (aria-hidden) unless a label is given. */
export function BrailleCell({
  pattern = [true, true, true, true, true, true],
  loading = false,
  label,
}: {
  pattern?: readonly [boolean, boolean, boolean, boolean, boolean, boolean];
  loading?: boolean;
  label?: string;
}) {
  // Reading order 1,4,2,5,3,6 maps to a row-major 2x3 grid.
  const order = [0, 3, 1, 4, 2, 5];
  return (
    <span
      className={`${styles.cell}${loading ? ` ${styles.spin}` : ""}`}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      {order.map((dotIndex, position) => (
        <span
          key={dotIndex}
          className={`${styles.dot} ${pattern[dotIndex] ? styles.on : ""}`}
          style={loading ? { animationDelay: `${(position * 1100) / 6}ms` } : undefined}
        />
      ))}
    </span>
  );
}

export const BULLET_PATTERN = [true, false, false, false, false, false] as const;
export const DIVIDER_PATTERN = [true, true, true, true, true, true] as const;
