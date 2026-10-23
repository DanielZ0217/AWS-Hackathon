import { TERMINAL_EVENT_TYPES } from "../events/schema";
import { API_BASE } from "./api";
import type { ConnectionStatus, EventSourceLike, SourceListener } from "./types";

function isTerminal(data: unknown): boolean {
  if (typeof data !== "object" || data === null) return false;
  const type = (data as { type?: unknown }).type;
  return typeof type === "string" && (TERMINAL_EVENT_TYPES as readonly string[]).includes(type);
}

function parse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text; // forwarded as-is; the state builder records it as a rejected message
  }
}

// Starts a run on the backend and streams its events (Server-Sent Events).
// The browser's EventSource reconnects by itself and resumes from the last event id it saw.
export class LiveSource implements EventSourceLike {
  readonly kind = "live" as const;

  private readonly presetId: string;
  private readonly baseUrl: string;
  private listeners = new Set<SourceListener>();
  private status: ConnectionStatus = "idle";
  private stream: EventSource | null = null;
  private generation = 0; // bumps on every start/stop so callbacks from an older run are ignored

  constructor(presetId: string, baseUrl: string = API_BASE) {
    this.presetId = presetId;
    this.baseUrl = baseUrl;
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  subscribe(listener: SourceListener): () => void {
    this.listeners.add(listener);
    this.call(listener, (l) => l.onStatus(this.status));
    return () => {
      this.listeners.delete(listener);
    };
  }

  start(): void {
    if (this.status === "connecting" || this.status === "live") return; // already running
    this.closeStream();
    const generation = ++this.generation;
    this.forEach((l) => l.onReset());
    this.setStatus("connecting");
    void this.open(generation);
  }

  stop(): void {
    this.generation += 1;
    this.closeStream();
    this.setStatus("idle");
  }

  private async open(generation: number): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset_id: this.presetId }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const body = (await response.json()) as { run_id?: string };
      if (typeof body.run_id !== "string") throw new Error("no run id in the response");
      if (generation !== this.generation) return; // stopped or restarted while waiting

      const stream = new EventSource(`${this.baseUrl}/runs/${encodeURIComponent(body.run_id)}/events`);
      this.stream = stream;
      stream.onopen = () => {
        if (generation === this.generation) this.setStatus("live");
      };
      stream.onmessage = (message: MessageEvent<string>) => {
        if (generation !== this.generation) return;
        const data = parse(message.data);
        this.forEach((l) => l.onMessage(data));
        if (isTerminal(data)) {
          this.closeStream(); // stop the browser from reconnecting once the run is over
          this.setStatus("ended");
        }
      };
      stream.onerror = () => {
        if (generation !== this.generation) return;
        // CLOSED means the browser gave up; otherwise it is retrying on its own.
        this.setStatus(stream.readyState === EventSource.CLOSED ? "error" : "connecting");
      };
    } catch {
      if (generation === this.generation) this.setStatus("error");
    }
  }

  private closeStream(): void {
    this.stream?.close();
    this.stream = null;
  }

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.forEach((l) => l.onStatus(status));
  }

  private forEach(fn: (listener: SourceListener) => void): void {
    for (const listener of [...this.listeners]) this.call(listener, fn);
  }

  private call(listener: SourceListener, fn: (listener: SourceListener) => void): void {
    try {
      fn(listener);
    } catch (error) {
      console.error("LiveSource listener threw", error);
    }
  }
}
