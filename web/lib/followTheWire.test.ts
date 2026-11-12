import { describe, expect, it } from "vitest";
import { followTheWireOrder } from "@/lib/followTheWire";
import type { Circuit, CircuitComponent, CircuitNet } from "@/lib/types";

function comp(id: string, category = "resistor"): CircuitComponent {
  return {
    id,
    category,
    bbox: null,
    flags: {
      component_id: id,
      level: "no concern",
      strong_flags: [],
      weak_flags: [],
      verifier_p_wrong: null,
      reasons: [],
    },
  };
}

function net(id: string, components: string[]): CircuitNet {
  return { id, label: id, fanout: components.length, components };
}

function circuit(components: CircuitComponent[], nets: CircuitNet[]): Circuit {
  return {
    id: "test",
    image: "test.png",
    image_width: null,
    image_height: null,
    components,
    nets,
    flags: { circuit: { no_ground: false, no_supply: false, rail_conflict: false }, flagged_count: 0 },
    explanation: { layer1_overview: [], layer2_blocks: [], layer3_details: [] },
    flagged_count: 0,
    evaluation: {
      evaluation_only: true,
      ned: 0,
      ned_lower_bound: 0,
      graph_isomorphic: true,
      connection_precision: 1,
      connection_recall: 1,
      true_error_count: 0,
      true_error_component_ids: [],
      note: "",
    },
  };
}

describe("followTheWireOrder", () => {
  it("starts at a supply/source component when present", () => {
    const c = circuit(
      [comp("C1", "resistor"), comp("C2", "voltage"), comp("C3", "resistor")],
      [net("n1", ["C2", "C1"]), net("n2", ["C1", "C3"])],
    );
    expect(followTheWireOrder(c)[0]).toBe("C2");
  });

  it("starts at the first component in reading order when there is no source", () => {
    const c = circuit(
      [comp("C1"), comp("C2"), comp("C3")],
      [net("n1", ["C1", "C2"]), net("n2", ["C2", "C3"])],
    );
    expect(followTheWireOrder(c)[0]).toBe("C1");
  });

  it("walks breadth-first to neighbours in reading order", () => {
    // C1 - C2, C1 - C3, C2 - C4 : from C1, visit C2 then C3 (both one
    // hop, reading order), then C4 (two hops).
    const c = circuit(
      [comp("C1"), comp("C2"), comp("C3"), comp("C4")],
      [net("n1", ["C1", "C2"]), net("n2", ["C1", "C3"]), net("n3", ["C2", "C4"])],
    );
    expect(followTheWireOrder(c)).toEqual(["C1", "C2", "C3", "C4"]);
  });

  it("covers disconnected islands by restarting at the next unvisited component", () => {
    const c = circuit(
      [comp("C1"), comp("C2"), comp("C3"), comp("C4")],
      [net("n1", ["C1", "C2"]), net("n2", ["C3", "C4"])],
    );
    expect(followTheWireOrder(c)).toEqual(["C1", "C2", "C3", "C4"]);
  });

  it("visits every component exactly once", () => {
    const c = circuit(
      [comp("C1"), comp("C2"), comp("C3")],
      [net("n1", ["C1", "C2", "C3"])],
    );
    const order = followTheWireOrder(c);
    expect(new Set(order).size).toBe(3);
    expect(order).toHaveLength(3);
  });
});
