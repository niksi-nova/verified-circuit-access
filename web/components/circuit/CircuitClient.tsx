"use client";

import { useEffect, useState } from "react";
import { ControlsPanel, type LineSpacing, type TextSize } from "@/components/circuit/ControlsPanel";
import { Downloads } from "@/components/circuit/Downloads";
import { ModeToggle, type Mode } from "@/components/circuit/ModeToggle";
import { ReaderMode } from "@/components/circuit/ReaderMode";
import { ReviewMode } from "@/components/circuit/ReviewMode";
import { ShortcutsDialog } from "@/components/circuit/ShortcutsDialog";
import { StatusStamp } from "@/components/StatusStamp";
import { areShortcutsDisabled, setShortcutsDisabled } from "@/lib/shortcuts";
import { deriveStatus, loadReview } from "@/lib/reviewState";
import type { Circuit } from "@/lib/types";
import styles from "./CircuitClient.module.css";

export function CircuitClient({
  circuit,
  availableTextLayers,
  verifierNote,
}: {
  circuit: Circuit;
  availableTextLayers: string[];
  verifierNote: string;
}) {
  const [mode, setMode] = useState<Mode>("reader");
  const [textSize, setTextSize] = useState<TextSize>("normal");
  const [lineSpacing, setLineSpacing] = useState<LineSpacing>("normal");
  const [shortcutsOff, setShortcutsOff] = useState(false);
  const [shortcutsDialogOpen, setShortcutsDialogOpen] = useState(false);
  const [status, setStatus] = useState<"unreviewed" | "needs-check" | "teacher-confirmed">(
    "unreviewed",
  );

  useEffect(() => {
    // localStorage is browser-only; sync once after mount.
    /* eslint-disable react-hooks/set-state-in-effect */
    setShortcutsOff(areShortcutsDisabled(window.localStorage));
    const review = loadReview(circuit.id, window.localStorage);
    setStatus(deriveStatus(circuit.flagged_count, review));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [circuit.id, circuit.flagged_count]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "?" && !shortcutsOff) {
        setShortcutsDialogOpen(true);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [shortcutsOff]);

  function updateShortcutsOff(disabled: boolean) {
    setShortcutsOff(disabled);
    setShortcutsDisabled(disabled, window.localStorage);
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h1>
          Circuit {circuit.id} <StatusStamp status={status} />
        </h1>
        <ModeToggle mode={mode} onChange={setMode} />
      </div>

      <ControlsPanel
        textSize={textSize}
        onTextSize={setTextSize}
        lineSpacing={lineSpacing}
        onLineSpacing={setLineSpacing}
        shortcutsDisabled={shortcutsOff}
        onShortcutsDisabled={updateShortcutsOff}
        onOpenShortcuts={() => setShortcutsDialogOpen(true)}
      />
      <ShortcutsDialog open={shortcutsDialogOpen} onOpenChange={setShortcutsDialogOpen} />

      {mode === "reader" ? (
        <ReaderMode
          circuit={circuit}
          textSize={textSize}
          lineSpacing={lineSpacing}
          shortcutsDisabled={shortcutsOff}
        />
      ) : (
        <ReviewMode circuit={circuit} />
      )}

      <Downloads circuitId={circuit.id} availableTextLayers={availableTextLayers} />

      <p
        style={{
          color: "var(--color-text-muted)",
          fontSize: "0.8rem",
          marginTop: "var(--space-4)",
        }}
      >
        {verifierNote}
      </p>
    </div>
  );
}
