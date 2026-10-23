import { useEffect, useReducer } from "react";
import { initialStreamState, streamReducer } from "./streamReducer";
import type { StreamState } from "./streamReducer";
import type { EventSourceLike } from "./types";

// Connects a source to the screen state. It does not start the source: a button (or the caller)
// does that. Cleanup unsubscribes and stops, so it is safe under React's development double-mount.
export function useRunStream(source: EventSourceLike | null): StreamState {
  const [state, dispatch] = useReducer(streamReducer, undefined, initialStreamState);

  useEffect(() => {
    dispatch({ type: "reset" });
    dispatch({ type: "status", status: "idle" });
    if (!source) return;

    const unsubscribe = source.subscribe({
      onMessage: (raw) => dispatch({ type: "message", raw }),
      onStatus: (status) => dispatch({ type: "status", status }),
      onReset: () => dispatch({ type: "reset" }),
    });
    return () => {
      unsubscribe();
      source.stop();
    };
  }, [source]);

  return state;
}
