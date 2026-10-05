import { describe, expect, it, vi } from "vitest";
import { createInitialState, Store } from "../src/state/store";

describe("Store", () => {
  it("initializes with animationIndex at full length (fully built)", () => {
    const state = createInitialState(42);
    expect(state.animationIndex).toBe(42);
    expect(state.selectedStitchId).toBeNull();
    expect(state.viewMode).toBe("yarn");
  });

  it("merges patches without discarding untouched fields", () => {
    const store = new Store(createInitialState(10));
    store.set({ selectedStitchId: "abc" });
    store.set({ opacity: 0.5 });
    const state = store.get();
    expect(state.selectedStitchId).toBe("abc");
    expect(state.opacity).toBe(0.5);
    expect(state.animationIndex).toBe(10);
  });

  it("notifies subscribers on every set, and unsubscribe stops notifications", () => {
    const store = new Store(createInitialState(5));
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);

    store.set({ opacity: 0.8 });
    expect(listener).toHaveBeenCalledTimes(1);

    unsubscribe();
    store.set({ opacity: 0.2 });
    expect(listener).toHaveBeenCalledTimes(1);
  });
});
