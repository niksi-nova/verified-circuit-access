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
  textDownloads,
}: {
  textDownloads: Record<string, string>;
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
