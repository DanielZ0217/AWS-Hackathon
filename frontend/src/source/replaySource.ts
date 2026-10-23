import type { Scenario } from "../mock/scenarios";
import type { ConnectionStatus, EventSourceLike, SourceListener } from "./types";

// Replays a scripted scenario. Each event waits its own `delayMs` (divided by the speed) after
// the previous one. The timer chain is one setTimeout at a time, which makes pause simple:
// remember how much of the current wait is left, and wait only that long on resume.
export class ReplaySource implements EventSourceLike {
  readonly kind = "replay" as const;

  private readonly scenario: Scenario;
  private listeners = new Set<SourceListener>();
  private status: ConnectionStatus = "idle";
  private speed: number;
  private nextIndex = 0; // index of the next event to emit
  private timer: ReturnType<typeof setTimeout> | null = null;
  private remainingMs = 0; // UNSCALED ms left in the current wait
  private waitStartedAt = 0; // Date.now() when the current wait began

  constructor(scenario: Scenario, speed = 1) {
    this.scenario = scenario;
    this.speed = speed > 0 && Number.isFinite(speed) ? speed : 1;
  }

  get progress(): { emitted: number; total: number } {
    return { emitted: this.nextIndex, total: this.scenario.events.length };
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  subscribe(listener: SourceListener): () => void {
    this.listeners.add(listener);
    this.call(listener, (l) => l.onStatus(this.status)); // sync the new listener
    return () => {
      this.listeners.delete(listener);
    };
  }

  start(): void {
    if (this.status === "live" || this.status === "paused") return; // already running
    this.begin();
  }

  restart(): void {
    this.begin();
  }

  stop(): void {
    this.clearTimer();
    this.setStatus("idle");
  }

  pause(): void {
    if (this.status !== "live") return;
    this.freezeRemaining();
    this.setStatus("paused");
  }

  resume(): void {
    if (this.status !== "paused") return;
    this.setStatus("live");
    this.schedule(this.remainingMs);
  }

  setSpeed(speed: number): void {
    if (!(speed > 0) || !Number.isFinite(speed)) return; // ignore nonsense values
    if (this.status === "live") {
      // Rescale the rest of the current wait so the change takes effect immediately.
      this.freezeRemaining();
      this.speed = speed;
      this.schedule(this.remainingMs);
    } else {
      this.speed = speed;
    }
  }

  // --- internals -----------------------------------------------------------

  private begin(): void {
    this.clearTimer();
    this.nextIndex = 0;
    this.forEach((l) => l.onReset());
    this.setStatus("live");
    this.schedule(this.scenario.events[0]?.delayMs ?? 0);
  }

  private schedule(unscaledMs: number): void {
    this.remainingMs = unscaledMs;
    this.waitStartedAt = Date.now();
    this.timer = setTimeout(() => this.fire(), unscaledMs / this.speed);
  }

  private fire(): void {
    this.timer = null;
    const item = this.scenario.events[this.nextIndex];
    if (!item) {
      this.setStatus("ended");
      return;
    }
    this.nextIndex += 1;
    // A copy, so nothing downstream can modify the scenario data.
    const message = structuredClone(item.event);
    this.forEach((l) => l.onMessage(message));

    const next = this.scenario.events[this.nextIndex];
    if (next) this.schedule(next.delayMs);
    else this.setStatus("ended");
  }

  // Work out how much of the current wait is left (in unscaled ms) and cancel the timer.
  private freezeRemaining(): void {
    if (this.timer === null) return;
    const elapsedScaled = Date.now() - this.waitStartedAt;
    this.remainingMs = Math.max(0, this.remainingMs - elapsedScaled * this.speed);
    this.clearTimer();
  }

  private clearTimer(): void {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.forEach((l) => l.onStatus(status));
  }

  private forEach(fn: (listener: SourceListener) => void): void {
    for (const listener of [...this.listeners]) this.call(listener, fn);
  }

  // One misbehaving listener must not stop the replay or starve the others.
  private call(listener: SourceListener, fn: (listener: SourceListener) => void): void {
    try {
      fn(listener);
    } catch (error) {
      console.error("ReplaySource listener threw", error);
    }
  }
}
