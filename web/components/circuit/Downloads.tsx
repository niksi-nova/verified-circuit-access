"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { CalculationResult, type SpiceResult } from "./Calculation";
import type { Circuit } from "@/lib/types";
import styles from "./Downloads.module.css";

const LAYER_LABELS: Record<string, string> = {
  layer1: "Overview (layer 1)",
  layer2: "Possible blocks (layer 2)",
  layer3: "Part-by-part detail (layer 3)",
  all: "All layers",
};

export function Downloads({
  textDownloads,
  circuit,
  calculation,
  onReview,
}: {
  textDownloads: Record<string, string>;
  circuit: Circuit;
  calculation?: SpiceResult;
  onReview: () => void;
}) {
  return (
    <Tabs.Root defaultValue="text" className={styles.tabs}>
      <Tabs.List className={styles.tabList} aria-label="Downloads and other outputs">
        <Tabs.Trigger className={styles.tabTrigger} value="text">
          Text layers
        </Tabs.Trigger>
        <Tabs.Trigger className={styles.tabTrigger} value="braille">
          Braille preview
        </Tabs.Trigger>
        <Tabs.Trigger className={styles.tabTrigger} value="tactile">
          Raised diagram
        </Tabs.Trigger>
        <Tabs.Trigger className={styles.tabTrigger} value="ngspice">
          Calculation
        </Tabs.Trigger>
      </Tabs.List>

      <Tabs.Content value="text" className={styles.tabContent}>
        {Object.keys(textDownloads).length === 0 ? (
          <p className={styles.notRun}>not run</p>
        ) : (
          Object.entries(textDownloads).map(([layer, url]) => (
            <a
              key={layer}
              className={styles.downloadLink}
              href={url}
              download
            >
              {LAYER_LABELS[layer] ?? layer}
            </a>
          ))
        )}
      </Tabs.Content>

      <Tabs.Content value="braille" className={styles.tabContent}>
        {circuit.braille ? (
          <>
            <p>Liblouis table {circuit.braille.table}. This output is not proofread by a braille reader.</p>
            <a className={styles.downloadLink}
              href={`data:application/octet-stream,${encodeURIComponent(circuit.braille.brf)}`}
              download={`circuit-${circuit.id}.brf`}>
              Download BRF
            </a>
            {circuit.braille.pages.map((page, i) => (
              <figure className={styles.braillePage} key={i}>
                <figcaption>Page {i + 1}</figcaption>
                <pre>{page}</pre>
              </figure>
            ))}
          </>
        ) : <p className={styles.notRun}>not run</p>}
      </Tabs.Content>

      <Tabs.Content value="tactile" className={styles.tabContent}>
        <p className={styles.notRun}>not run</p>
      </Tabs.Content>

      <Tabs.Content value="ngspice" className={styles.tabContent}>
        {calculation ? <CalculationResult result={calculation} /> : (
          <>
            <p className={styles.notRun}>not run</p>
            <button type="button" onClick={onReview}>Open teacher review to add values</button>
          </>
        )}
      </Tabs.Content>
    </Tabs.Root>
  );
}
