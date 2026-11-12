"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/engine";

interface Outputs {
  braille: boolean;
  tactile: boolean;
  ngspice_available: boolean;
}

export function OutputStatus({ libraryBraille, libraryTactile }: {
  libraryBraille: boolean;
  libraryTactile: boolean;
}) {
  const [local, setLocal] = useState<Outputs>();
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2500);
    void api<{ outputs: Outputs }>("health", { signal: controller.signal })
      .then((health) => setLocal(health.outputs), () => {})
      .finally(() => clearTimeout(timer));
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);

  return (
    <section aria-labelledby="output-status">
      <h2 id="output-status">Output status</h2>
      <ul>
        <li>Braille (.brf) — {libraryBraille || local?.braille ? "generated" : "not run"}</li>
        <li>Raised-diagram SVG — {libraryTactile || local?.tactile ? "generated" : "not run"}</li>
        <li>ngspice electrical calculations — {local?.ngspice_available
          ? "simulator available. Enter values in teacher review to run a calculation."
          : "not run. The local simulator is unavailable."}</li>
      </ul>
    </section>
  );
}
