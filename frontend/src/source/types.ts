// Anything that produces workflow events implements EventSourceLike: the scripted replay now,
// the live SSE client later. The screens only know this interface.

export type ConnectionStatus = "idle" | "connecting" | "live" | "paused" | "ended" | "error";

export interface SourceListener {
  onMessage(raw: unknown): void; // an untyped message; the state builder validates it
  onStatus(status: ConnectionStatus): void;
  onReset(): void; // a new run is starting: clear the screen
}

export interface EventSourceLike {
  readonly kind: "replay" | "live"; // drives the REPLAY badge
  subscribe(listener: SourceListener): () => void; // returns an unsubscribe function
  start(): void;
  stop(): void;
}
