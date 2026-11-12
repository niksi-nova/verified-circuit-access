"use client";

import * as Tabs from "@radix-ui/react-tabs";
import styles from "./Downloads.module.css";

const LAYER_LABELS: Record<string, string> = {
  layer1: "Overview (layer 1)",
  layer2: "Possible blocks (layer 2)",
  layer3: "Part-by-part detail (layer 3)",
  all: "All layers",
};

export function Downloads({
  circuitId,
  availableTextLayers,
}: {
  circuitId: string;
  availableTextLayers: string[];
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
          Tactile SVG
        </Tabs.Trigger>
        <Tabs.Trigger className={styles.tabTrigger} value="ngspice">
          ngspice values
        </Tabs.Trigger>
      </Tabs.List>

      <Tabs.Content value="text" className={styles.tabContent}>
        {availableTextLayers.length === 0 ? (
          <p className={styles.notRun}>not run</p>
        ) : (
          availableTextLayers.map((layer) => (
            <a
              key={layer}
              className={styles.downloadLink}
              href={`/data/text/${circuitId}.${layer}.txt`}
              download
            >
              {LAYER_LABELS[layer] ?? layer}
            </a>
          ))
        )}
      </Tabs.Content>

      <Tabs.Content value="braille" className={styles.tabContent}>
        <p>40 cells per line layout is built; no .brf file exists yet for this circuit.</p>
        <p className={styles.notRun}>not run</p>
      </Tabs.Content>

      <Tabs.Content value="tactile" className={styles.tabContent}>
        <p className={styles.notRun}>not run</p>
      </Tabs.Content>

      <Tabs.Content value="ngspice" className={styles.tabContent}>
        <p className={styles.notRun}>not run</p>
      </Tabs.Content>
    </Tabs.Root>
  );
}
