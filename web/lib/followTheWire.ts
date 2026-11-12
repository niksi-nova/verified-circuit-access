import type { Circuit } from "@/lib/types";

const SOURCE_CATEGORIES = new Set(["voltage", "current", "vdd"]);

/**
 * "Follow the wire" order — deterministic, documented, unit-tested.
 *
 * 1. Start at the first source/supply-category component (voltage,
 *    current or vdd) in the circuit's reading order (top-left to
 *    bottom-right, as already fixed by the backend); if there is none,
 *    start at the first component in reading order (top-left).
 * 2. From the current component, visit its unvisited neighbours —
 *    components sharing any net with it — in reading-order, breadth
 *    first (so one step away comes entirely before two steps away).
 * 3. When a connected region is exhausted, continue from the next
 *    unvisited component in reading order (a fresh BFS), so every
 *    component appears exactly once even across disconnected islands.
 *
 * The result is a total order over all component ids.
 */
export function followTheWireOrder(circuit: Circuit): string[] {
  const components = circuit.components;
  const indexOf = new Map(components.map((c, i) => [c.id, i]));

  const neighbors = new Map<string, Set<string>>();
  for (const comp of components) neighbors.set(comp.id, new Set());
  for (const net of circuit.nets) {
    for (const a of net.components) {
      for (const b of net.components) {
        if (a !== b) neighbors.get(a)?.add(b);
      }
    }
  }

  function sortedNeighbors(id: string): string[] {
    return [...(neighbors.get(id) ?? [])].sort(
      (a, b) => (indexOf.get(a) ?? 0) - (indexOf.get(b) ?? 0),
    );
  }

  const visited = new Set<string>();
  const order: string[] = [];

  function bfsFrom(startId: string) {
    const queue = [startId];
    visited.add(startId);
    while (queue.length > 0) {
      const current = queue.shift() as string;
      order.push(current);
      for (const next of sortedNeighbors(current)) {
        if (!visited.has(next)) {
          visited.add(next);
          queue.push(next);
        }
      }
    }
  }

  const firstSource = components.find((c) => SOURCE_CATEGORIES.has(c.category));
  if (firstSource) bfsFrom(firstSource.id);

  for (const comp of components) {
    if (!visited.has(comp.id)) bfsFrom(comp.id);
  }

  return order;
}
