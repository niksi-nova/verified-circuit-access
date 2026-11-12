"use client";

import { useEffect, useState } from "react";
import * as Switch from "@radix-ui/react-switch";
import { DiagramOverlay } from "@/components/circuit/DiagramOverlay";
import { plainName } from "@/lib/plainNames";
import {
  loadReview,
  saveReview,
  setComponentDecision,
  signOff,
  type CircuitReview,
} from "@/lib/reviewState";
import type { Circuit } from "@/lib/types";
import controlStyles from "./ControlsPanel.module.css";
import styles from "./ReviewMode.module.css";

export function ReviewMode({ circuit }: { circuit: Circuit }) {
  const [review, setReview] = useState<CircuitReview>({ signedOff: false, components: {} });
  const [evaluationVisible, setEvaluationVisible] = useState(false);
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [highlightIds, setHighlightIds] = useState<string[]>([]);

  useEffect(() => {
    // localStorage is browser-only; sync once after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReview(loadReview(circuit.id, window.localStorage));
  }, [circuit.id]);

  const flagged = circuit.components.filter((c) => c.flags.level === "needs check");
  const rest = circuit.components.filter((c) => c.flags.level !== "needs check");

  function confirm(id: string) {
    setReview(setComponentDecision(circuit.id, id, "confirmed", undefined, window.localStorage));
  }

  function markWrong(id: string) {
    const note = noteDrafts[id]?.trim();
    setReview(setComponentDecision(circuit.id, id, "wrong", note, window.localStorage));
  }

  function doSignOff() {
    setReview(signOff(circuit.id, window.localStorage));
  }

  function unsign() {
    const next = { ...review, signedOff: false, signedOffAt: undefined };
    saveReview(circuit.id, next, window.localStorage);
    setReview(next);
  }

  const evaluation = circuit.evaluation;
  const trueErrorSet = new Set(evaluation?.true_error_component_ids);
  const flaggedSet = new Set(flagged.map((c) => c.id));
  const missedErrors = evaluation?.true_error_component_ids.filter((id) => !flaggedSet.has(id));

  return (
    <div>
      <div className={styles.layout}>
        <div>
          <DiagramOverlay
            circuit={circuit}
            highlightIds={highlightIds}
            onSelect={(id) => setHighlightIds([id])}
          />
        </div>

        <div>
          <h2>Flagged parts ({flagged.length})</h2>
          {flagged.length === 0 && <p>No parts were flagged.</p>}
          <ul className={styles.list}>
            {[...flagged, ...rest].map((c) => {
              const decision = review.components[c.id];
              const isFlagged = c.flags.level === "needs check";
              return (
                <li
                  key={c.id}
                  className={`${styles.part} ${isFlagged ? styles.flaggedPart : ""}`}
                  onFocus={() => setHighlightIds([c.id])}
                  onMouseEnter={() => setHighlightIds([c.id])}
                >
                  {isFlagged && (
                    <span className={styles.marginMark} aria-hidden="true">
                      ✎
                    </span>
                  )}
                  <strong>
                    {c.id} — {plainName(c.category)}
                  </strong>
                  {c.flags.reasons.length > 0 && (
                    <ul className={styles.reasons}>
                      {c.flags.reasons.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  )}
                  <div className={styles.actions}>
                    <button type="button" onClick={() => confirm(c.id)}>
                      Confirm
                    </button>
                    <input
                      className={styles.noteInput}
                      placeholder="Note for 'mark as wrong' (optional)"
                      value={noteDrafts[c.id] ?? ""}
                      onChange={(e) =>
                        setNoteDrafts((prev) => ({ ...prev, [c.id]: e.target.value }))
                      }
                      aria-label={`Note for ${c.id}`}
                    />
                    <button type="button" onClick={() => markWrong(c.id)}>
                      Mark as wrong
                    </button>
                    {decision && (
                      <span className={styles.decision}>
                        saved: {decision.decision}
                        {decision.note ? ` — "${decision.note}"` : ""}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          <div className={styles.signOff}>
            {review.signedOff ? (
              <>
                <p>
                  Signed off {review.signedOffAt ? `on ${new Date(review.signedOffAt).toLocaleString()}` : ""}.
                </p>
                <button type="button" onClick={unsign}>
                  Undo sign-off
                </button>
              </>
            ) : (
              <button type="button" onClick={doSignOff}>
                Sign off this circuit
              </button>
            )}
            <p className={styles.storageNote}>
              Decisions and sign-off are saved in this browser only (localStorage). The
              netlist itself is never edited here — these are notes only.
            </p>
          </div>

          {evaluation && <div className={controlStyles.group} style={{ marginBottom: "var(--space-3)" }}>
            <label htmlFor="evaluation-toggle">
              Evaluation view (research only) — not available for new circuits
            </label>
            <Switch.Root
              id="evaluation-toggle"
              className={controlStyles.switchRoot}
              checked={evaluationVisible}
              onCheckedChange={setEvaluationVisible}
            >
              <Switch.Thumb className={controlStyles.switchThumb} />
            </Switch.Root>
          </div>}

          {evaluation && evaluationVisible && (
            <section className={styles.evaluationPanel} aria-label="Evaluation view">
              <span className={styles.evalLabel}>Evaluation only — ground truth</span>
              <h2>How this circuit actually scored</h2>
              <ul>
                <li>NED: {evaluation.ned} (lower bound {evaluation.ned_lower_bound})</li>
                <li>Netlist exactly right: {evaluation.graph_isomorphic ? "yes" : "no"}</li>
                <li>Connection precision / recall: {evaluation.connection_precision} / {evaluation.connection_recall}</li>
                <li>Real errors: {evaluation.true_error_count}</li>
              </ul>
              <p>
                Flagged parts that are real errors:{" "}
                {flagged.filter((c) => trueErrorSet.has(c.id)).map((c) => c.id).join(", ") || "none"}
              </p>
              <p>
                Flagged parts that are not real errors (false positives):{" "}
                {flagged.filter((c) => !trueErrorSet.has(c.id)).map((c) => c.id).join(", ") || "none"}
              </p>
              <p>
                Real errors that were not flagged (missed):{" "}
                {missedErrors?.join(", ") || "none"}
              </p>
              <p>{evaluation.note}</p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
