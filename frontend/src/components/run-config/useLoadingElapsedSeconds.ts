import { useEffect, useState } from "react";

export const useLoadingElapsedSeconds = (loading: boolean): number => {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!loading) {
      setElapsedSeconds(0);
      return undefined;
    }

    const startedAtMs = Date.now();
    setElapsedSeconds(0);
    const timer = window.setInterval(() => {
      setElapsedSeconds((Date.now() - startedAtMs) / 1000);
    }, 100);

    return () => window.clearInterval(timer);
  }, [loading]);

  return elapsedSeconds;
};
