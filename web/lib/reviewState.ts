import type { ReviewStatus } from "@/lib/types";

export const REVIEW_KEY_PREFIX = "braille-press:review:";
export const SHORTCUTS_DISABLED_KEY = "braille-press:shortcuts-disabled";

export type ComponentDecision = "confirmed" | "wrong";

export interface ComponentReviewNote {
  decision: ComponentDecision;
  note?: string;
  decidedAt: string;
}

export interface CircuitReview {
  signedOff: boolean;
  signedOffAt?: string;
  components: Record<string, ComponentReviewNote>;
}

const EMPTY_REVIEW: CircuitReview = { signedOff: false, components: {} };

/** Storage is injected so this logic is testable without a real DOM. */
export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function loadReview(id: string, storage: KeyValueStorage): CircuitReview {
  try {
    const raw = storage.getItem(REVIEW_KEY_PREFIX + id);
    if (!raw) return EMPTY_REVIEW;
    const parsed = JSON.parse(raw) as Partial<CircuitReview>;
    return { ...EMPTY_REVIEW, ...parsed };
  } catch {
    return EMPTY_REVIEW;
  }
}

export function saveReview(id: string, review: CircuitReview, storage: KeyValueStorage): void {
  storage.setItem(REVIEW_KEY_PREFIX + id, JSON.stringify(review));
}

export function setComponentDecision(
  id: string,
  componentId: string,
  decision: ComponentDecision,
  note: string | undefined,
  storage: KeyValueStorage,
): CircuitReview {
  const review = loadReview(id, storage);
  const next: CircuitReview = {
    ...review,
    components: {
      ...review.components,
      [componentId]: { decision, note, decidedAt: new Date().toISOString() },
    },
  };
  saveReview(id, next, storage);
  return next;
}

export function signOff(id: string, storage: KeyValueStorage): CircuitReview {
  const review = loadReview(id, storage);
  const next: CircuitReview = {
    ...review,
    signedOff: true,
    signedOffAt: new Date().toISOString(),
  };
  saveReview(id, next, storage);
  return next;
}

/** Pure status derivation: never reads ground truth, only the saved
 * review and the circuit's own (non-ground-truth) flagged_count. */
export function deriveStatus(flaggedCount: number, review: CircuitReview): ReviewStatus {
  if (review.signedOff) return "teacher-confirmed";
  if (flaggedCount > 0) return "needs-check";
  return "unreviewed";
}
