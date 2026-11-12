"use client";

import * as Switch from "@radix-ui/react-switch";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CircuitClient } from "@/components/circuit/CircuitClient";
import controlStyles from "@/components/circuit/ControlsPanel.module.css";
import { api, useEngineStatus } from "@/lib/engine";
import type { Circuit } from "@/lib/types";
import styles from "./TryFlow.module.css";

const EXAMPLES = ["002", "003", "014", "015", "019", "095"];
const LAYERS = ["layer1", "layer2", "layer3", "all"];
const STAGES: Record<string, string> = {
  read_image: "Reading the image",
  detect_components: "Detecting components",
  detect_crossings: "Detecting wire crossings",
  orientation: "Reading component orientation",
  netting: "Tracing wires and building nets",
  rule_checks: "Checking circuit rules",
  verifier: "Scoring parts for review",
  explanation: "Building the explanation",
};

interface Run {
  sha256: string;
  timestamp: string;
  duration_seconds: number;
}

interface Result {
  result: Circuit;
  from_saved: boolean;
  saved_timestamp: string;
}

interface Job extends Partial<Result> {
  status: "queued" | "running" | "done" | "error" | "cancelled";
  stage: string | null;
  elapsed_seconds: number;
  error?: string;
}

function tryUrl(run: string | null, job?: string) {
  if (!run) return "/try";
  const query = new URLSearchParams({ run });
  if (job) query.set("job", job);
  return `/try?${query}`;
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function typicalDuration(runs: Run[]) {
  const times = runs.map((run) => run.duration_seconds).sort((a, b) => a - b);
  const middle = Math.floor(times.length / 2);
  return times.length % 2 ? times[middle] : (times[middle - 1] + times[middle]) / 2;
}

export function TryFlow() {
  const params = useSearchParams();
  const run = params.get("run");
  const jobId = params.get("job");
  const engine = useEngineStatus();
  const [runs, setRuns] = useState<Run[]>([]);
  const [useSaved, setUseSaved] = useState(true);
  const [progress, setProgress] = useState<Job>();
  const [result, setResult] = useState<(Result & { run: string })>();
  const [pending, setPending] = useState<{ name: string; load: () => Promise<Blob> }>();
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const uploadInFlight = useRef(false);
  const ready = engine === "ready";

  useEffect(() => {
    if (!ready) return;
    let active = true;
    void api<Run[]>("runs").then((list) => { if (active) setRuns(list); }, () => {});
    return () => { active = false; };
  }, [ready, result]);

  useEffect(() => {
    if (!ready || !run || (!jobId && result?.run === run)) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();

    async function load() {
      try {
        if (!jobId) {
          const saved = await api<Result>(`runs/${run}`, { signal: controller.signal });
          if (active && run) setResult({ ...saved, run });
          return;
        }
        const job = await api<Job>(`jobs/${jobId}`, { signal: controller.signal });
        if (!active || !run) return;
        setProgress(job);
        if (job.status === "done" && job.result && job.saved_timestamp) {
          setResult({
            run,
            result: job.result,
            from_saved: Boolean(job.from_saved),
            saved_timestamp: job.saved_timestamp,
          });
          setCancelling(false);
          window.history.replaceState(null, "", tryUrl(run));
        } else if (job.status === "error" || job.status === "cancelled") {
          setCancelling(false);
          if (job.error) setError(job.error);
          if (job.status === "cancelled") setNotice("Analysis cancelled.");
          window.history.replaceState(null, "", tryUrl(null));
        } else {
          timer = setTimeout(load, 350);
        }
      } catch (cause) {
        if (!active) return;
        setError(message(cause));
        setCancelling(false);
        window.history.replaceState(null, "", tryUrl(jobId ? run : null));
      }
    }
    void load();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [ready, run, jobId, result]);

  const current = ready && !busy && !jobId && result?.run === run ? result : undefined;
  useEffect(() => {
    if (current) heading.current?.focus();
  }, [current]);

  async function submit(getImage: () => Promise<Blob>, saved: boolean) {
    if (!ready || uploadInFlight.current || jobId) return;
    uploadInFlight.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    setProgress(undefined);
    try {
      const image = await getImage();
      if (image.size > 10 * 1024 * 1024) throw new Error("The image is larger than 10 MB.");
      const form = new FormData();
      form.set("file", image);
      form.set("use_saved", String(saved));
      const job = await api<{ job_id: string; sha256: string }>("analyze", {
        method: "POST",
        body: form,
      });
      setResult(undefined);
      setPending(undefined);
      window.history.pushState(null, "", tryUrl(job.sha256, job.job_id));
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
      uploadInFlight.current = false;
    }
  }

  function selectImage(name: string, load: () => Promise<Blob>) {
    setError("");
    setPending({ name, load });
    if (ready) void submit(load, useSaved);
  }

  async function fetchImage(url: string) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error("The image could not be opened.");
    return response.blob();
  }

  async function cancel() {
    setCancelling(true);
    try {
      await api(`jobs/${jobId}/cancel`, { method: "POST" });
    } catch (cause) {
      setError(message(cause));
      setCancelling(false);
    }
  }

  async function deleteRun(id: string) {
    setError("");
    try {
      await api(`runs/${id}`, { method: "DELETE" });
      if (run === id) reset();
      setRuns((list) => list.filter((entry) => entry.sha256 !== id));
      setNotice("Saved analysis deleted.");
    } catch (cause) {
      setError(message(cause));
    }
  }

  function reset() {
    setResult(undefined);
    setPending(undefined);
    setError("");
    setNotice("");
    window.history.pushState(null, "", tryUrl(null));
  }

  const progressLabel = busy ? "Sending image to the local engine"
    : progress?.status === "queued" ? "Waiting for the current analysis to finish"
    : STAGES[progress?.stage ?? ""] ?? "Waiting for the engine";

  return (
    <div className={styles.wrap}>
      <h1>Try it</h1>
      <div role="status" aria-live="polite" className={styles.status}>
        {engine === "offline" ? "The local analysis engine is offline."
          : engine === "starting" ? "The local analysis engine is starting."
          : notice}
      </div>
      {error && <p className={styles.alert} role="alert">{error}</p>}

      {ready && (busy || jobId) ? (
        <section aria-labelledby="reading-heading">
          <h2 id="reading-heading">2. Reading the circuit</h2>
          <p role="status" aria-live="polite">{cancelling ? "Cancelling analysis…" : progressLabel}</p>
          <p>Elapsed: {progress?.elapsed_seconds ?? 0} seconds.</p>
          {runs.length > 0 && <p>Usually about {Math.round(typicalDuration(runs))} seconds.</p>}
          <button type="button" disabled={!jobId || cancelling} onClick={cancel}>Cancel</button>
        </section>
      ) : current && run ? (
        <section aria-labelledby="result-heading">
          <h2 id="result-heading" ref={heading} tabIndex={-1}>3. Result</h2>
          <p className={styles.banner}>Machine-read, not yet checked by a teacher</p>
          {current.from_saved && (
            <p>
              Saved result from {new Date(current.saved_timestamp).toLocaleString()}.{" "}
              <button type="button" onClick={() => submit(() => fetchImage(`/api/runs/${run}/image`), false)}>
                Run again
              </button>
            </p>
          )}
          {current.result.warnings?.map((warning) => <p key={warning}>{warning}</p>)}
          <CircuitClient
            key={`${run}:${current.saved_timestamp}`}
            embedded
            circuit={{ ...current.result, image_url: `/api/runs/${run}/image?v=${encodeURIComponent(current.saved_timestamp)}` }}
            textDownloads={Object.fromEntries(LAYERS.map((layer) => [layer, `/api/runs/${run}/text/${layer}`]))}
            verifierNote={`Verifier source: ${current.result.verifier_source ?? "unavailable"}`}
          />
          <button type="button" onClick={reset}>Analyse another image</button>
        </section>
      ) : ready && run ? (
        <p role="status">Opening saved analysis…</p>
      ) : (
        <section aria-labelledby="add-heading">
          <h2 id="add-heading">1. Add an image</h2>
          <div
            className={styles.drop}
            data-dragging={dragging}
            onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              const file = event.dataTransfer.files[0];
              if (file) selectImage(file.name, async () => file);
            }}
            onPaste={(event) => {
              const file = event.clipboardData.files[0];
              if (file) {
                event.preventDefault();
                selectImage(file.name || "Clipboard image", async () => file);
              }
            }}
          >
            <p>Drop an image here or focus the button and paste from the clipboard.</p>
            <p>PNG or JPEG, up to 10 MB. The image stays on this computer.</p>
            <input
              hidden ref={input} type="file" accept="image/png,image/jpeg,.jpg,.jpeg,.png"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                event.currentTarget.value = "";
                if (file) selectImage(file.name, async () => file);
              }}
            />
            <button type="button" onClick={() => input.current?.click()}>Choose an image</button>
          </div>

          {pending && (
            <div>
              <p role="status">{pending.name} selected. {ready ? "Ready to send." : "Waiting for the local engine."}</p>
              <button type="button" disabled={!ready} onClick={() => submit(pending.load, useSaved)}>
                Analyse selected image
              </button>
            </div>
          )}

          <h3>Examples</h3>
          <p>These examples come from our evaluation set. How well this works on new textbook figures has not been measured yet.</p>
          <ul className={styles.examples}>
            {EXAMPLES.map((id) => (
              <li key={id}>
                <button type="button" onClick={() => selectImage(`Example ${id}`, () => fetchImage(`/api/examples/${id}`))}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`/api/examples/${id}`} alt="" width={108} height={76} />
                  Example {id}
                </button>
              </li>
            ))}
          </ul>
          <div className={controlStyles.group}>
            <Switch.Root id="use-saved" className={controlStyles.switchRoot} checked={useSaved} onCheckedChange={setUseSaved}>
              <Switch.Thumb className={controlStyles.switchThumb} />
            </Switch.Root>
            <label htmlFor="use-saved">Use the saved result if this image was analysed before</label>
          </div>
        </section>
      )}

      {ready && (
        <section className={styles.recent} aria-labelledby="recent-heading">
          <h2 id="recent-heading">Recent analyses</h2>
          {runs.length === 0 ? <p>No saved analyses.</p> : (
            <ul>
              {runs.map((entry) => (
                <li key={entry.sha256}>
                  <a href={tryUrl(entry.sha256)}>
                    {new Date(entry.timestamp).toLocaleString()} ({entry.sha256.slice(0, 8)})
                  </a>{" "}
                  <button type="button" disabled={Boolean(jobId) || busy} aria-label={`Delete analysis ${entry.sha256.slice(0, 8)}`} onClick={() => deleteRun(entry.sha256)}>
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
