import { SHORTCUTS_DISABLED_KEY, type KeyValueStorage } from "@/lib/reviewState";

/** WCAG 2.1.4: single-key shortcuts must be possible to turn off, and
 * must never fire while the focus is on a text input / textarea /
 * contenteditable / select. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable === true ||
    target.contentEditable === "true"
  );
}

export function areShortcutsDisabled(storage: KeyValueStorage): boolean {
  return storage.getItem(SHORTCUTS_DISABLED_KEY) === "true";
}

export function setShortcutsDisabled(disabled: boolean, storage: KeyValueStorage): void {
  storage.setItem(SHORTCUTS_DISABLED_KEY, disabled ? "true" : "false");
}
