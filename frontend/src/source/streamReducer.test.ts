import { describe, expect, it } from "vitest";
import { getScenario } from "../mock/scenarios";
import { initialStreamState, streamReducer } from "./streamReducer";

const cleanEvents = getScenario("clean")!.events.map((s) => s.event);

describe("streamReducer", () => {
  it("accumulates messages into the run", () => {
    let state = initialStreamState();
    for (const event of cleanEvents.slice(0, 5)) state = streamReducer(state, { type: "message", raw: event });
    expect(state.run.events).toHaveLength(5);
    expect(state.run.status).toBe("running");
  });

  it("records a malformed message in rejected without throwing", () => {
    const state = streamReducer(initialStreamState(), { type: "message", raw: { nonsense: true } });
    expect(state.run.rejected).toHaveLength(1);
    expect(state.run.events).toHaveLength(0);
  });

  it("returns the same state for a repeated message", () => {
    const once = streamReducer(initialStreamState(), { type: "message", raw: cleanEvents[0] });
    expect(streamReducer(once, { type: "message", raw: cleanEvents[0] })).toBe(once);
  });

  it("reset clears the run and the rejected list but keeps the status", () => {
    let state = initialStreamState();
    state = streamReducer(state, { type: "status", status: "live" });
    state = streamReducer(state, { type: "message", raw: cleanEvents[0] });
    state = streamReducer(state, { type: "message", raw: { bad: true } });
    state = streamReducer(state, { type: "reset" });
    expect(state.run.events).toHaveLength(0);
    expect(state.run.rejected).toHaveLength(0);
    expect(state.run.status).toBe("idle");
    expect(state.status).toBe("live");
  });

  it("a replay after reset rebuilds the run instead of being ignored as duplicates", () => {
    let state = initialStreamState();
    for (const event of cleanEvents) state = streamReducer(state, { type: "message", raw: event });
    state = streamReducer(state, { type: "reset" });
    for (const event of cleanEvents) state = streamReducer(state, { type: "message", raw: event });
    expect(state.run.status).toBe("completed");
    expect(state.run.events).toHaveLength(cleanEvents.length);
  });

  it("status updates apply, and an identical status keeps the same state object", () => {
    const live = streamReducer(initialStreamState(), { type: "status", status: "live" });
    expect(live.status).toBe("live");
    expect(streamReducer(live, { type: "status", status: "live" })).toBe(live);
  });
});
