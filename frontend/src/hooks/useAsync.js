import { useEffect, useState } from "react";

// Runs an async loader on mount; returns { data, loading, error, live }.
export function useAsync(loader, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null, live: false });

  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true }));
    Promise.resolve(loader())
      .then((res) => {
        if (!alive) return;
        // loader may return {data, live} (withFallback) or a raw value
        if (res && typeof res === "object" && "live" in res && "data" in res) {
          setState({ data: res.data, loading: false, error: null, live: res.live });
        } else {
          setState({ data: res, loading: false, error: null, live: true });
        }
      })
      .catch((err) => alive && setState({ data: null, loading: false, error: err, live: false }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
