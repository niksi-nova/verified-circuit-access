export type FlagLevel = "needs check" | "no concern";

export interface ComponentFlags {
  component_id: string;
  level: FlagLevel;
  strong_flags: string[];
  weak_flags: string[];
  verifier_p_wrong: number | null;
  reasons: string[];
}

export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CircuitComponent {
  id: string;
  category: string;
  bbox: BBox | null;
  flags: ComponentFlags;
}

export interface CircuitNet {
  id: string;
  label: string;
  fanout: number;
  components: string[];
}

export interface ExplanationSentence {
  text: string;
  components: string[];
  nets: string[];
}

export interface CircuitFlags {
  circuit: {
    no_ground: boolean;
    no_supply: boolean;
    rail_conflict: boolean;
  };
  flagged_count: number;
}

export interface Evaluation {
  evaluation_only: true;
  ned: number;
  ned_lower_bound: number;
  graph_isomorphic: boolean;
  connection_precision: number;
  connection_recall: number;
  true_error_count: number;
  true_error_component_ids: string[];
  note: string;
}

export interface Circuit {
  id: string;
  image: string;
  image_width: number | null;
  image_height: number | null;
  components: CircuitComponent[];
  nets: CircuitNet[];
  flags: CircuitFlags;
  explanation: {
    layer1_overview: ExplanationSentence[];
    layer2_blocks: ExplanationSentence[];
    layer3_details: ExplanationSentence[];
  };
  flagged_count: number;
  evaluation?: Evaluation | null;
  image_url?: string;
  verifier_source?: string;
  warnings?: string[];
}

export type ReviewStatus = "unreviewed" | "needs-check" | "teacher-confirmed";

export type MetricsBlock = Record<string, unknown> | "not available";

export interface StatusData {
  pipeline: MetricsBlock;
  verifier: MetricsBlock;
  detector: MetricsBlock;
  crossing: MetricsBlock;
  orientation: MetricsBlock;
  verifier_note: string;
}
