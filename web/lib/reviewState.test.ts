import { beforeEach, describe, expect, it } from "vitest";
import {
  deriveStatus,
  loadReview,
  saveReview,
  setComponentDecision,
  signOff,
  type KeyValueStorage,
} from "@/lib/reviewState";

function fakeStorage(): KeyValueStorage {
  const store = new Map<string, string>();
  return {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, value),
  };
}

describe("deriveStatus", () => {
  it("is unreviewed when nothing is flagged and nothing is saved", () => {
    expect(deriveStatus(0, { signedOff: false, components: {} })).toBe("unreviewed");
  });

  it("is needs-check when flagged_count > 0 and not signed off", () => {
    expect(deriveStatus(3, { signedOff: false, components: {} })).toBe("needs-check");
  });

  it("is teacher-confirmed once signed off, regardless of flag count", () => {
    expect(deriveStatus(5, { signedOff: true, components: {} })).toBe("teacher-confirmed");
  });
});

describe("review localStorage state", () => {
  let storage: KeyValueStorage;

  beforeEach(() => {
    storage = fakeStorage();
  });

  it("loadReview returns an empty review when nothing is saved", () => {
    expect(loadReview("001", storage)).toEqual({ signedOff: false, components: {} });
  });

  it("round-trips through saveReview/loadReview", () => {
    saveReview("001", { signedOff: true, components: {} }, storage);
    expect(loadReview("001", storage).signedOff).toBe(true);
  });

  it("setComponentDecision records a decision and preserves others", () => {
    setComponentDecision("001", "C1", "wrong", "looks shorted", storage);
    const review = setComponentDecision("001", "C2", "confirmed", undefined, storage);
    expect(review.components.C1.decision).toBe("wrong");
    expect(review.components.C1.note).toBe("looks shorted");
    expect(review.components.C2.decision).toBe("confirmed");
  });

  it("signOff sets signedOff and a timestamp, without touching component notes", () => {
    setComponentDecision("001", "C1", "confirmed", undefined, storage);
    const review = signOff("001", storage);
    expect(review.signedOff).toBe(true);
    expect(review.signedOffAt).toBeTruthy();
    expect(review.components.C1.decision).toBe("confirmed");
  });

  it("is isolated per circuit id", () => {
    setComponentDecision("001", "C1", "wrong", undefined, storage);
    expect(loadReview("002", storage).components).toEqual({});
  });
});
