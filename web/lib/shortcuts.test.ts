import { describe, expect, it } from "vitest";
import { areShortcutsDisabled, isTypingTarget, setShortcutsDisabled } from "@/lib/shortcuts";
import type { KeyValueStorage } from "@/lib/reviewState";

function fakeStorage(): KeyValueStorage {
  const store = new Map<string, string>();
  return {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, value),
  };
}

describe("isTypingTarget", () => {
  it("is true for input, textarea, select and contenteditable", () => {
    expect(isTypingTarget(document.createElement("input"))).toBe(true);
    expect(isTypingTarget(document.createElement("textarea"))).toBe(true);
    expect(isTypingTarget(document.createElement("select"))).toBe(true);
    const div = document.createElement("div");
    div.contentEditable = "true";
    expect(isTypingTarget(div)).toBe(true);
  });

  it("is false for ordinary elements and null", () => {
    expect(isTypingTarget(document.createElement("div"))).toBe(false);
    expect(isTypingTarget(document.createElement("button"))).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
  });
});

describe("shortcut disabling persists", () => {
  it("defaults to enabled (not disabled)", () => {
    expect(areShortcutsDisabled(fakeStorage())).toBe(false);
  });

  it("round-trips through setShortcutsDisabled/areShortcutsDisabled", () => {
    const storage = fakeStorage();
    setShortcutsDisabled(true, storage);
    expect(areShortcutsDisabled(storage)).toBe(true);
    setShortcutsDisabled(false, storage);
    expect(areShortcutsDisabled(storage)).toBe(false);
  });
});
