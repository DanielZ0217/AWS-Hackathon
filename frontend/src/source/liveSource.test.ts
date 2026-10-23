import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchPresets } from "./api";
import { LiveSource } from "./liveSource";
import type { ConnectionStatus } from "./types";

// A stand-in for the browser's EventSource, so tests control exactly what the "server" sends.
class FakeEventSource {
  static readonly CLOSED = 2;
  static instances: FakeEventSource[] = [];
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  url: string;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  close() {
    this.readyState = FakeEventSource.CLOSED;
  }
  send(data: unknown) {
    this.onmessage?.({ data: typeof data === "string" ? data : JSON.stringify(data) });
  }
}

function setup(runId: string | null = "run-1") {
  const fetchMock = vi.fn(async () =>
    runId === null ? { ok: false, status: 500, json: async () => ({}) } : { ok: true, status: 200, json: async () => ({ run_id: runId }) },
  );
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("EventSource", FakeEventSource);
  const source = new LiveSource("demo-001");
  const seen = { messages: [] as unknown[], statuses: [] as ConnectionStatus[], resets: 0 };
  source.subscribe({
    onMessage: (raw) => seen.messages.push(raw),
    onStatus: (s) => seen.statuses.push(s),
    onReset: () => {
      seen.resets += 1;
    },
  });
  return { source, seen, fetchMock };
}

beforeEach(() => {
  FakeEventSource.instances = [];
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LiveSource", () => {
  it("posts the preset id, opens a stream for the returned run, and reports live on open", async () => {
    const { source, seen, fetchMock } = setup("run-42");
    source.start();
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    expect(fetchMock).toHaveBeenCalledWith("/api/runs", expect.objectContaining({ method: "POST", body: JSON.stringify({ preset_id: "demo-001" }) }));
    expect(FakeEventSource.instances[0].url).toBe("/api/runs/run-42/events");
    expect(seen.statuses).toEqual(["idle", "connecting"]);
    FakeEventSource.instances[0].onopen?.();
    expect(seen.statuses.at(-1)).toBe("live");
    expect(seen.resets).toBe(1);
  });

  it("forwards parsed messages, and forwards non-JSON text as a string", async () => {
    const { source, seen } = setup();
    source.start();
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    FakeEventSource.instances[0].send({ type: "run.started", sequence: 1 });
    FakeEventSource.instances[0].send("not json");
    expect(seen.messages).toEqual([{ type: "run.started", sequence: 1 }, "not json"]);
  });

  it("closes the stream and ends when the terminal event arrives", async () => {
    const { source, seen } = setup();
    source.start();
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    FakeEventSource.instances[0].send({ type: "run.completed", sequence: 9 });
    expect(FakeEventSource.instances[0].readyState).toBe(FakeEventSource.CLOSED);
    expect(seen.statuses.at(-1)).toBe("ended");
  });

  it("reports an error, without throwing, when the backend refuses the run", async () => {
    const { source, seen } = setup(null);
    source.start();
    await vi.waitFor(() => expect(seen.statuses.at(-1)).toBe("error"));
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it("reports an error when the network call itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    vi.stubGlobal("EventSource", FakeEventSource);
    const source = new LiveSource("demo-001");
    const statuses: ConnectionStatus[] = [];
    source.subscribe({ onMessage: () => {}, onStatus: (s) => statuses.push(s), onReset: () => {} });
    source.start();
    await vi.waitFor(() => expect(statuses.at(-1)).toBe("error"));
  });

  it("stop closes the stream and ignores anything the old stream sends afterwards", async () => {
    const { source, seen } = setup();
    source.start();
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    source.stop();
    FakeEventSource.instances[0].send({ type: "worker.started", sequence: 3 });
    expect(seen.messages).toEqual([]);
    expect(seen.statuses.at(-1)).toBe("idle");
    expect(FakeEventSource.instances[0].readyState).toBe(FakeEventSource.CLOSED);
  });

  it("starting again after the run ended resets the screen and opens a fresh stream", async () => {
    const { source, seen } = setup();
    source.start();
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    FakeEventSource.instances[0].send({ type: "run.completed", sequence: 1 });
    source.start();
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(2));
    expect(seen.resets).toBe(2);
  });

  it("does not start a second run while one is in progress", async () => {
    const { source, fetchMock } = setup();
    source.start();
    source.start();
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("fetchPresets", () => {
  it("returns the presets when the backend answers", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => [{ id: "a", label: "A", description: "d" }, { bad: true }] })));
    expect(await fetchPresets()).toEqual([{ id: "a", label: "A", description: "d" }]);
  });

  it("returns null on a failed request or a bad response", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new Error("down"))));
    expect(await fetchPresets()).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, json: async () => [] })));
    expect(await fetchPresets()).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ not: "an array" }) })));
    expect(await fetchPresets()).toBeNull();
  });
});
