import { useCallback, useEffect, useRef, useState } from 'react';
import { errorMessage } from '../api/client.js';

/**
 * Run an async function on mount and whenever `deps` change.
 * Returns { data, loading, error, reload, refresh }.
 *  - reload():  shows the loading state again
 *  - refresh(): silent background refresh (keeps existing data on screen)
 * Pass { refreshMs } to poll silently.
 */
export default function useAsync(fn, deps = [], { refreshMs } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const requestId = useRef(0);

  const load = useCallback(async (silent = false) => {
    const id = ++requestId.current;
    if (!silent) setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fnRef.current();
      if (id === requestId.current) setState({ data, loading: false, error: null });
    } catch (err) {
      if (id === requestId.current) {
        setState((s) => ({ data: silent ? s.data : null, loading: false, error: silent ? null : errorMessage(err) }));
      }
    }
  }, []);

  useEffect(() => {
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (!refreshMs) return undefined;
    const timer = setInterval(() => load(true), refreshMs);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshMs, load, ...deps]);

  useEffect(
    () => () => {
      requestId.current = -1; // ignore responses that arrive after unmount
    },
    []
  );

  return { ...state, reload: () => load(false), refresh: () => load(true) };
}
