import type { StitchGeometry } from "../types/geometry";

/** Drives construction animation strictly from graph sequence order, never spatial proximity. */
export class ConstructionTimeline {
  readonly orderedStitchIds: string[];
  private index: number;
  private playing = false;
  private speed: number; // stitches per second
  private accumulator = 0;
  private lastTime = 0;
  private onChange: (index: number) => void;

  constructor(stitches: StitchGeometry[], onChange: (index: number) => void, speed = 60) {
    this.orderedStitchIds = [...stitches]
      .sort((a, b) => a.sequence_index - b.sequence_index)
      .map((s) => s.stitch_id);
    this.index = this.orderedStitchIds.length;
    this.speed = speed;
    this.onChange = onChange;
  }

  get length(): number {
    return this.orderedStitchIds.length;
  }

  get currentIndex(): number {
    return this.index;
  }

  setIndex(index: number): void {
    this.index = Math.max(0, Math.min(this.orderedStitchIds.length, Math.round(index)));
    this.onChange(this.index);
  }

  setSpeed(stitchesPerSecond: number): void {
    this.speed = Math.max(1, stitchesPerSecond);
  }

  /**
   * @param now Current time in the same clock `tick()` will be called with.
   * Defaults to `performance.now()` for real usage; callers that drive the
   * timeline with an explicit/fake clock (e.g. tests) must pass a matching
   * value here too, or the first `tick()` delta will be computed against
   * the wrong epoch.
   */
  play(now: number = performance.now()): void {
    this.playing = true;
    this.lastTime = now;
    this.accumulator = 0;
  }

  pause(): void {
    this.playing = false;
  }

  restart(): void {
    this.setIndex(0);
    this.play();
  }

  stepForward(): void {
    this.setIndex(this.index + 1);
  }

  stepBackward(): void {
    this.setIndex(this.index - 1);
  }

  get isPlaying(): boolean {
    return this.playing;
  }

  /** Call once per animation frame; advances `index` when playing. */
  tick(now: number): void {
    if (!this.playing) return;
    const deltaSeconds = (now - this.lastTime) / 1000;
    this.lastTime = now;
    this.accumulator += deltaSeconds * this.speed;
    if (this.accumulator >= 1) {
      const step = Math.floor(this.accumulator);
      this.accumulator -= step;
      const next = this.index + step;
      if (next >= this.orderedStitchIds.length) {
        this.setIndex(this.orderedStitchIds.length);
        this.playing = false;
      } else {
        this.setIndex(next);
      }
    }
  }
}
