import { createInitialState, ingestRaw } from "../state/runState";
import type { RunState } from "../state/runState";
import type { ConnectionStatus } from "./types";

// Screen-level state: the run plus the connection status. A plain reducer, so it is testable
// without React.

export interface StreamState {
  run: RunState;
  status: ConnectionStatus;
}

export type StreamAction =
  | { type: "message"; raw: unknown }
  | { type: "status"; status: ConnectionStatus }
  | { type: "reset" };

export function initialStreamState(): StreamState {
  return { run: createInitialState(), status: "idle" };
}

export function streamReducer(state: StreamState, action: StreamAction): StreamState {
  switch (action.type) {
    case "message": {
      const run = ingestRaw(state.run, action.raw);
      return run === state.run ? state : { ...state, run };
    }
    case "status":
      return state.status === action.status ? state : { ...state, status: action.status };
    case "reset":
      // Clears the run, including the rejected list. The status is set separately.
      return { ...state, run: createInitialState() };
  }
}
