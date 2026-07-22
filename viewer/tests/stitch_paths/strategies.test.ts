import { describe, expect, it } from "vitest";
import { generateStitchPaths, supportedStitchTypes } from "../../src/geometry/stitch_paths/strategies";
import { makeContextWithStitches, makeStitch } from "./factory";

function allFinite(numbers: number[]): boolean {
  return numbers.every((n) => Number.isFinite(n));
}

function flattenPoints(result: ReturnType<typeof generateStitchPaths>): number[] {
  return result.segments.flatMap((s) => s.controlPoints.flat());
}

describe("supportedStitchTypes", () => {
  it("includes every stitch the brief requires geometry for", () => {
    const types = supportedStitchTypes();
    expect(types).toEqual(expect.arrayContaining(["sc", "hdc", "dc", "chain", "slip_stitch"]));
  });
});

describe.each(["sc", "hdc", "dc"] as const)("%s strategy", (stitchType) => {
  it("produces finite control points", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: stitchType, parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(allFinite(flattenPoints(result))).toBe(true);
  });

  it("has a positive radius on every segment", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: stitchType, parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    for (const segment of result.segments) expect(segment.radius).toBeGreaterThan(0);
  });

  it("includes a post and a top_loop role", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: stitchType, parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    const roles = result.segments.map((s) => s.role);
    expect(roles).toContain("post");
    expect(roles).toContain("top_loop");
  });

  it("produces identical output for identical input (deterministic)", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: stitchType, parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, stitch]);
    const a = generateStitchPaths(stitch, context);
    const b = generateStitchPaths(stitch, context);
    expect(a).toEqual(b);
  });

  it("has a valid entry and exit point", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: stitchType, parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(allFinite(result.entryPoint)).toBe(true);
    expect(allFinite(result.exitPoint)).toBe(true);
  });
});

describe("relative stitch height (post length)", () => {
  function postLength(stitchType: "sc" | "hdc" | "dc"): number {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: stitchType, parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    const post = result.segments.find((s) => s.role === "post");
    if (!post) throw new Error("no post segment");
    const [start, end] = [post.controlPoints[0], post.controlPoints[post.controlPoints.length - 1]];
    return Math.hypot(start[0] - end[0], start[1] - end[1], start[2] - end[2]);
  }

  it("orders sc < hdc < dc", () => {
    const sc = postLength("sc");
    const hdc = postLength("hdc");
    const dc = postLength("dc");
    expect(sc).toBeLessThan(hdc);
    expect(hdc).toBeLessThan(dc);
  });
});

describe("wrap count (yarn_over segments)", () => {
  function wrapCount(stitchType: "sc" | "hdc" | "dc"): number {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: stitchType, parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, stitch]);
    return generateStitchPaths(stitch, context).segments.filter((s) => s.role === "yarn_over").length;
  }

  it("sc has none, hdc has one, dc has two", () => {
    expect(wrapCount("sc")).toBe(0);
    expect(wrapCount("hdc")).toBe(1);
    expect(wrapCount("dc")).toBe(2);
  });
});

describe("loop placement", () => {
  it("both loops: no warning, no front_loop/back_loop segment", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ parent_stitch_ids: ["parent"], loop_placement: "both" });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.warnings).toHaveLength(0);
    expect(result.segments.map((s) => s.role)).not.toContain("front_loop");
    expect(result.segments.map((s) => s.role)).not.toContain("back_loop");
  });

  it("front_loop_only: emits a front_loop segment and a warning", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ parent_stitch_ids: ["parent"], loop_placement: "front_loop_only" });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.segments.map((s) => s.role)).toContain("front_loop");
    expect(result.warnings.length).toBeGreaterThan(0);
  });

  it("back_loop_only: emits a back_loop segment and a warning", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ parent_stitch_ids: ["parent"], loop_placement: "back_loop_only" });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.segments.map((s) => s.role)).toContain("back_loop");
    expect(result.warnings.length).toBeGreaterThan(0);
  });

  it("front and back loop offsets are on opposite sides", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const front = makeStitch({ parent_stitch_ids: ["parent"], loop_placement: "front_loop_only" });
    const back = makeStitch({ parent_stitch_ids: ["parent"], loop_placement: "back_loop_only" });
    const context = makeContextWithStitches([parent, front, back]);
    const frontSeg = generateStitchPaths(front, context).segments.find((s) => s.role === "front_loop")!;
    const backSeg = generateStitchPaths(back, context).segments.find((s) => s.role === "back_loop")!;
    // Their attach points must differ (opposite lateral offset).
    expect(frontSeg.controlPoints[1]).not.toEqual(backSeg.controlPoints[1]);
  });

  it("both loops: loopAttachment reports exact (no approximation needed)", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ parent_stitch_ids: ["parent"], loop_placement: "both" });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.loopAttachment.requested).toBe("both");
    expect(result.loopAttachment.exact).toBe(true);
  });

  it("front_loop_only: loopAttachment reports a fallback, not exact", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ parent_stitch_ids: ["parent"], loop_placement: "front_loop_only" });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.loopAttachment.requested).toBe("front_loop_only");
    expect(result.loopAttachment.exact).toBe(false);
    expect(result.loopAttachment.resolved).toMatch(/approximation/);
  });

  it("back_loop_only: loopAttachment reports a fallback, not exact", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ parent_stitch_ids: ["parent"], loop_placement: "back_loop_only" });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.loopAttachment.requested).toBe("back_loop_only");
    expect(result.loopAttachment.exact).toBe(false);
  });

  it("no parent (magic ring root): loopAttachment is exact regardless of requested placement", () => {
    const stitch = makeStitch({ parent_stitch_ids: [], loop_placement: "front_loop_only" });
    const context = makeContextWithStitches([stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.loopAttachment.exact).toBe(true);
    expect(result.loopAttachment.resolved).toMatch(/magic ring/);
  });

  it("chain: non-'both' loop placement is flagged as unmodelled, not silently dropped", () => {
    const stitch = makeStitch({ stitch_type: "chain", loop_placement: "front_loop_only" });
    const context = makeContextWithStitches([stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.loopAttachment.exact).toBe(false);
    expect(result.warnings.some((w) => w.includes("not modelled"))).toBe(true);
  });

  it("chain: 'both' loop placement needs no warning (it's the assumed default)", () => {
    const stitch = makeStitch({ stitch_type: "chain", loop_placement: "both" });
    const context = makeContextWithStitches([stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.loopAttachment.exact).toBe(true);
    expect(result.warnings).toHaveLength(0);
  });

  it("slip stitch: non-'both' loop placement is flagged as unmodelled", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({
      stitch_type: "slip_stitch",
      parent_stitch_ids: ["parent"],
      loop_placement: "back_loop_only",
    });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.loopAttachment.exact).toBe(false);
    expect(result.warnings.some((w) => w.includes("not modelled"))).toBe(true);
  });
});

describe("increase", () => {
  it("both children reference the same parent and each has an increase_branch segment", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const childA = makeStitch({ parent_stitch_ids: ["parent"], is_increase: true });
    const childB = makeStitch({ parent_stitch_ids: ["parent"], is_increase: true });
    const context = makeContextWithStitches([parent, childA, childB]);
    const resultA = generateStitchPaths(childA, context);
    const resultB = generateStitchPaths(childB, context);
    expect(resultA.segments.map((s) => s.role)).toContain("increase_branch");
    expect(resultB.segments.map((s) => s.role)).toContain("increase_branch");
    const branchA = resultA.segments.find((s) => s.role === "increase_branch")!;
    const branchB = resultB.segments.find((s) => s.role === "increase_branch")!;
    // Both branches start from the same shared parent position.
    expect(branchA.controlPoints[0]).toEqual(branchB.controlPoints[0]);
    expect(branchA.controlPoints[0]).toEqual(parent.position);
  });

  it("children remain individually distinct (not overlapping) stitch IDs", () => {
    const childA = makeStitch({ parent_stitch_ids: ["parent"], is_increase: true });
    const childB = makeStitch({ parent_stitch_ids: ["parent"], is_increase: true });
    expect(childA.stitch_id).not.toBe(childB.stitch_id);
  });
});

describe("decrease", () => {
  it("consumes two parents and adds a converging decrease_bridge", () => {
    const parentA = makeStitch({ stitch_id: "parentA" });
    const parentB = makeStitch({ stitch_id: "parentB" });
    const child = makeStitch({ parent_stitch_ids: ["parentA", "parentB"], is_decrease: true });
    const context = makeContextWithStitches([parentA, parentB, child]);
    const result = generateStitchPaths(child, context);
    const bridges = result.segments.filter((s) => s.role === "decrease_bridge");
    expect(bridges.length).toBeGreaterThanOrEqual(2);
    // The bridge geometry must reference both parent positions somewhere.
    const allBridgePoints = bridges.flatMap((b) => b.controlPoints);
    expect(allBridgePoints).toEqual(expect.arrayContaining([parentA.position]));
    expect(allBridgePoints).toEqual(expect.arrayContaining([parentB.position]));
  });
});

describe("chain (synthetic, not yet parser-producible)", () => {
  it("produces a single closed foundation_loop", () => {
    const stitch = makeStitch({ stitch_type: "chain" });
    const context = makeContextWithStitches([stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.segments).toHaveLength(1);
    expect(result.segments[0].role).toBe("foundation_loop");
    expect(result.segments[0].closed).toBe(true);
    expect(result.strategyName).toBe("chain");
  });

  it("alternates loop plane by sequence_index parity (deterministic interlocking)", () => {
    const even = makeStitch({ stitch_type: "chain", sequence_index: 0 });
    const odd = makeStitch({ stitch_type: "chain", sequence_index: 1 });
    const context = makeContextWithStitches([even, odd]);
    const evenLoop = generateStitchPaths(even, context).segments[0].controlPoints;
    const oddLoop = generateStitchPaths(odd, context).segments[0].controlPoints;
    expect(evenLoop).not.toEqual(oddLoop);
  });
});

describe("slip stitch (synthetic, not yet parser-producible)", () => {
  it("has minimal vertical rise compared to a single crochet", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const slipStitch = makeStitch({ stitch_type: "slip_stitch", parent_stitch_ids: ["parent"] });
    const sc = makeStitch({ stitch_type: "sc", parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, slipStitch, sc]);

    const slipResult = generateStitchPaths(slipStitch, context);
    const scResult = generateStitchPaths(sc, context);
    const slipConnector = slipResult.segments.find((s) => s.role === "connector");
    const scPost = scResult.segments.find((s) => s.role === "post")!;
    const scHeight = Math.hypot(
      scPost.controlPoints[0][2] - scPost.controlPoints[scPost.controlPoints.length - 1][2],
    );
    if (slipConnector) {
      const slipHeight = Math.hypot(
        slipConnector.controlPoints[0][2] - slipConnector.controlPoints[1][2],
      );
      expect(slipHeight).toBeLessThan(scHeight);
    }
  });
});

describe("unsupported stitch_type fallback", () => {
  it("falls back to single-crochet geometry with an explicit warning, never silently", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: "double_treble_unknown", parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);
    expect(result.strategyName).toBe("single_crochet_fallback");
    expect(result.warnings.some((w) => w.includes("Unrecognised stitch_type"))).toBe(true);
  });
});
