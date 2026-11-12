"use client";

import * as Switch from "@radix-ui/react-switch";
import styles from "./ControlsPanel.module.css";

export type TextSize = "normal" | "large" | "x-large";
export type LineSpacing = "normal" | "relaxed" | "loose";

export function ControlsPanel({
  textSize,
  onTextSize,
  lineSpacing,
  onLineSpacing,
  shortcutsDisabled,
  onShortcutsDisabled,
  onOpenShortcuts,
}: {
  textSize: TextSize;
  onTextSize: (v: TextSize) => void;
  lineSpacing: LineSpacing;
  onLineSpacing: (v: LineSpacing) => void;
  shortcutsDisabled: boolean;
  onShortcutsDisabled: (v: boolean) => void;
  onOpenShortcuts: () => void;
}) {
  return (
    <div className={styles.panel} role="group" aria-label="Reading controls">
      <div className={styles.group}>
        <label htmlFor="text-size">Text size</label>
        <select
          id="text-size"
          value={textSize}
          onChange={(e) => onTextSize(e.target.value as TextSize)}
        >
          <option value="normal">Normal</option>
          <option value="large">Large</option>
          <option value="x-large">Extra large</option>
        </select>
      </div>
      <div className={styles.group}>
        <label htmlFor="line-spacing">Line spacing</label>
        <select
          id="line-spacing"
          value={lineSpacing}
          onChange={(e) => onLineSpacing(e.target.value as LineSpacing)}
        >
          <option value="normal">Normal</option>
          <option value="relaxed">Relaxed</option>
          <option value="loose">Loose</option>
        </select>
      </div>
      <div className={styles.group}>
        <label htmlFor="disable-shortcuts">Disable single-key shortcuts</label>
        <Switch.Root
          id="disable-shortcuts"
          className={styles.switchRoot}
          checked={shortcutsDisabled}
          onCheckedChange={onShortcutsDisabled}
        >
          <Switch.Thumb className={styles.switchThumb} />
        </Switch.Root>
      </div>
      <button
        type="button"
        className={styles.helpButton}
        aria-label="Show keyboard shortcuts"
        onClick={onOpenShortcuts}
      >
        ?
      </button>
    </div>
  );
}
