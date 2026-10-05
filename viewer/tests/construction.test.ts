import { describe, expect, it, vi } from "vitest";
import { ConstructionTimeline } from "../src/animation/construction";
import { makeTestGeometry } from "./fixtures";

describe("ConstructionTimeline", () => {
  it("orders stitches by sequence_index, not array order", () => {
    const doc = makeTestGeometry();
    const shuffled = [doc.stitches[2], doc.stitches[0], doc.stitches[1]];
    const onChange = vi.fn();
    const timeline = new ConstructionTimeline(shuffled, onChange);
    expect(timeline.orderedStitchIds).toEqual([
      "crown-r01-s000",
      "crown-r02-s000",
      "body-r10-s000",
    ]);
  });

  it("starts fully built (index === length)", () => {
    const doc = makeTestGeometry();
    const timeline = new ConstructionTimeline(doc.stitches, vi.fn());
    expect(timeline.currentIndex).toBe(timeline.length);
  });

  it("clamps setIndex to [0, length]", () => {
    const doc = makeTestGeometry();
    const onChange = vi.fn();
    const timeline = new ConstructionTimeline(doc.stitches, onChange);
    timeline.setIndex(-5);
    expect(timeline.currentIndex).toBe(0);
    timeline.setIndex(999);
    expect(timeline.currentIndex).toBe(timeline.length);
  });

  it("stepForward/stepBackward move by exactly one stitch", () => {
    const doc = makeTestGeometry();
    const timeline = new ConstructionTimeline(doc.stitches, vi.fn());
    timeline.setIndex(1);
    timeline.stepForward();
    expect(timeline.currentIndex).toBe(2);
    timeline.stepBackward();
    timeline.stepBackward();
    expect(timeline.currentIndex).toBe(0);
  });

  it("play/tick advances index over time and stops at the end", () => {
    const doc = makeTestGeometry();
    const timeline = new ConstructionTimeline(doc.stitches, vi.fn(), 100); // 100 stitches/sec
    timeline.setIndex(0);
    timeline.play(0);
    timeline.tick(1000); // 1 full second later -> should advance ~100 stitches, clamped to length
    expect(timeline.currentIndex).toBe(timeline.length);
    expect(timeline.isPlaying).toBe(false);
  });

  it("restart resets to zero and starts playing", () => {
    const doc = makeTestGeometry();
    const timeline = new ConstructionTimeline(doc.stitches, vi.fn());
    timeline.restart();
    expect(timeline.currentIndex).toBe(0);
    expect(timeline.isPlaying).toBe(true);
  });
});
