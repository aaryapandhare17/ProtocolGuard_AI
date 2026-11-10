import { useEffect, useState, useRef } from "react";
import { api } from "../services/admin";
export function useResource(path, revision = 0, interval = 10000) {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [nonce, setNonce] = useState(0);
  const previousPath = useRef(path);
  useEffect(() => {
    let active = true,
      controller;
    if (previousPath.current !== path) {
      setData(null);
      setError("");
      previousPath.current = path;
    }
    async function load() {
      controller?.abort();
      controller = new AbortController();
      try {
        const result = await api(path, { signal: controller.signal });
        if (active) {
          setData(result);
          setError("");
        }
      } catch (err) {
        if (active && err.name !== "AbortError") setError(err.message);
      }
    }
    load();
    const timer = interval ? setInterval(load, interval) : null;
    return () => {
      active = false;
      controller?.abort();
      if (timer) clearInterval(timer);
    };
  }, [path, revision, nonce, interval]);
  return { data, error, refresh: () => setNonce((value) => value + 1) };
}
export function useDebounce(value, delay = 250) {
  const [result, setResult] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setResult(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return result;
}
