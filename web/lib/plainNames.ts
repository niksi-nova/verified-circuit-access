/** Mirrors src/vca/explain/names.py for display only. The actual
 * explanation sentences already use plain names server-side; this is
 * just for UI labels (e.g. the follow-the-wire announcement, filters). */
const PLAIN_NAMES: Record<string, string> = {
  antenna: "antenna",
  capacitor: "capacitor",
  "cross-line-curved": "curved wire crossing",
  current: "current source",
  "diff-amp": "differential amplifier (single-ended output)",
  diode: "diode",
  ground: "ground symbol",
  inductor: "inductor",
  nmos: "N-channel transistor",
  npn: "NPN transistor",
  pmos: "P-channel transistor",
  pnp: "PNP transistor",
  port: "port",
  resistor: "resistor",
  "single-end-amp": "single-ended amplifier",
  "single-input-single-end-amp": "single-input amplifier",
  switch: "switch",
  vdd: "supply symbol",
  voltage: "voltage source",
  "voltage-lines": "voltage source (multi-line)",
  "differential-amplifier": "differential amplifier",
};

export function plainName(category: string): string {
  return PLAIN_NAMES[category] ?? `component of type ${category}`;
}
