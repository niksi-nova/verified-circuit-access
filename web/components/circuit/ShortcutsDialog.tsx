"use client";

import * as Dialog from "@radix-ui/react-dialog";
import styles from "./ShortcutsDialog.module.css";

const SHORTCUTS: Array<[string, string]> = [
  ["1 / 2 / 3", "Open the overview / blocks / details section"],
  ["Right arrow, Down arrow", "Follow the wire: next component"],
  ["Left arrow, Up arrow", "Follow the wire: previous component"],
  ["?", "Open this list"],
];

export function ShortcutsDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.content} aria-describedby={undefined}>
          <Dialog.Title>Keyboard shortcuts</Dialog.Title>
          <dl>
            {SHORTCUTS.map(([key, desc]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{desc}</dd>
              </div>
            ))}
          </dl>
          <p>
            Shortcuts never fire while typing in a text field, and can be turned off
            entirely in the controls panel.
          </p>
          <Dialog.Close className={styles.close}>Close</Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
