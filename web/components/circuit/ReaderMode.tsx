"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DiagramOverlay } from "@/components/circuit/DiagramOverlay";
import { followTheWireOrder } from "@/lib/followTheWire";
import { plainName } from "@/lib/plainNames";
import { isTypingTarget } from "@/lib/shortcuts";
import { speak, speechSupported } from "@/lib/speech";
import type { Circuit, ExplanationSentence } from "@/lib/types";
import type { LineSpacing, TextSize } from "./ControlsPanel";
import styles from "./ReaderMode.module.css";

const FONT_SCALE: Record<TextSize, number> = { normal: 1, large: 1.2, "x-large": 1.45 };
const LINE_SCALE: Record<LineSpacing, number> = {
  normal: 1.65,
  relaxed: 1.9,
  loose: 2.2,
};

function describeStep(circuit: Circuit, id: string): string {
  const comp = circuit.components.find((c) => c.id === id);
  if (!comp) return "";
  const nets = circuit.nets.filter((n) => n.components.includes(id));
  const connections = nets
    .map((n) => {
      const others = n.components.filter((other) => other !== id);
      return others.length > 0
        ? `${n.label} (with ${others.join(", ")})`
        : `${n.label} alone`;
    })
    .join("; ");
  const status = comp.flags.level === "needs check" ? "needs a check" : "no concern";
  return `${id}, a ${plainName(comp.category)}. Connects to ${connections || "nothing"}. Status: ${status}.`;
}

function SentenceRow({
  sentence,
  onShowSource,
}: {
  sentence: ExplanationSentence;
  onShowSource: (s: ExplanationSentence) => void;
}) {
  const hasSource = sentence.components.length > 0 || sentence.nets.length > 0;
  return (
    <p className={styles.sentence}>
      <span>{sentence.text}</span>
      {hasSource && (
        <button
          type="button"
          className={styles.sourceButton}
          onFocus={() => onShowSource(sentence)}
          onClick={() => onShowSource(sentence)}
        >
          source
        </button>
      )}
    </p>
  );
}

export function ReaderMode({
  circuit,
  textSize,
  lineSpacing,
  shortcutsDisabled,
}: {
  circuit: Circuit;
  textSize: TextSize;
  lineSpacing: LineSpacing;
  shortcutsDisabled: boolean;
}) {
  const [followIndex, setFollowIndex] = useState<number | null>(null);
  const [highlightIds, setHighlightIds] = useState<string[]>([]);
  const [announcement, setAnnouncement] = useState("");
  const canSpeak = useMemo(() => speechSupported(), []);
  const containerRef = useRef<HTMLDivElement>(null);
  const section1Ref = useRef<HTMLDetailsElement>(null);
  const section2Ref = useRef<HTMLDetailsElement>(null);
  const section3Ref = useRef<HTMLDetailsElement>(null);

  const order = useMemo(() => followTheWireOrder(circuit), [circuit]);

  const goTo = useCallback(
    (index: number) => {
      const clamped = Math.max(0, Math.min(order.length - 1, index));
      setFollowIndex(clamped);
      const id = order[clamped];
      setHighlightIds([id]);
      setAnnouncement(`Step ${clamped + 1} of ${order.length}. ${describeStep(circuit, id)}`);
    },
    [circuit, order],
  );

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (shortcutsDisabled || isTypingTarget(e.target)) return;
      if (e.key === "1" || e.key === "2" || e.key === "3") {
        const el = { "1": section1Ref, "2": section2Ref, "3": section3Ref }[e.key].current;
        if (el) el.open = !el.open;
      } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        e.preventDefault();
        goTo((followIndex ?? -1) + 1);
      } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        goTo((followIndex ?? 1) - 1);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [shortcutsDisabled, followIndex, goTo]);

  return (
    <div
      ref={containerRef}
      className={styles.layout}
      style={{
        fontSize: `calc(var(--size-body) * ${FONT_SCALE[textSize]})`,
        lineHeight: LINE_SCALE[lineSpacing],
      }}
    >
      <details className={styles.diagramDetails}>
        <summary>Show original diagram</summary>
        <DiagramOverlay circuit={circuit} highlightIds={highlightIds} />
      </details>

      <section className={styles.follow} aria-label="Follow the wire">
        <h2>Follow the wire</h2>
        <p>
          Steps through every part in a fixed order: starting from a supply or source
          part if there is one, then walking to each unvisited neighbour that shares a
          connection.
        </p>
        <div className={styles.followButtons}>
          <button type="button" onClick={() => goTo((followIndex ?? 0) - 1)} disabled={followIndex === null || followIndex === 0}>
            ← Previous
          </button>
          <button type="button" onClick={() => goTo((followIndex ?? -1) + 1)}>
            {followIndex === null ? "Start" : "Next →"}
          </button>
          {canSpeak && followIndex !== null && (
            <button
              type="button"
              className={styles.speakButton}
              onClick={() => speak(describeStep(circuit, order[followIndex]))}
            >
              Read this step aloud
            </button>
          )}
        </div>
        <p className={styles.announcement} aria-live="polite" role="status">
          {announcement}
        </p>
      </section>

      <details className={styles.section} ref={section1Ref} open>
        <summary>
          Overview <span className={styles.key}>1</span>
        </summary>
        {circuit.explanation.layer1_overview.map((s, i) => (
          <SentenceRow key={i} sentence={s} onShowSource={(s2) => setHighlightIds(s2.components)} />
        ))}
      </details>

      <details className={styles.section} ref={section2Ref}>
        <summary>
          Possible blocks <span className={styles.key}>2</span>
        </summary>
        {circuit.explanation.layer2_blocks.map((s, i) => (
          <SentenceRow key={i} sentence={s} onShowSource={(s2) => setHighlightIds(s2.components)} />
        ))}
      </details>

      <details className={styles.section} ref={section3Ref}>
        <summary>
          Part-by-part detail <span className={styles.key}>3</span>
        </summary>
        {circuit.explanation.layer3_details.map((s, i) => (
          <SentenceRow key={i} sentence={s} onShowSource={(s2) => setHighlightIds(s2.components)} />
        ))}
      </details>
    </div>
  );
}
