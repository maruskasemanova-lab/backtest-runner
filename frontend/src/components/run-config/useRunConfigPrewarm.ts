import { useCallback, useEffect, useRef, useState } from "react";

type PrewarmPlan = {
  keyPayload: Record<string, any>;
  chunkPayloads: Record<string, any>[];
};

type UseRunConfigPrewarmArgs = {
  buildPrewarmPlan: () => PrewarmPlan | null;
  formatPrewarmReadyMessage: (payload: Record<string, any>) => string;
  chunkMaxRetries: number;
  retryBaseMs: number;
};

export const useRunConfigPrewarm = ({
  buildPrewarmPlan,
  formatPrewarmReadyMessage,
  chunkMaxRetries,
  retryBaseMs,
}: UseRunConfigPrewarmArgs) => {
  const [prewarmStatus, setPrewarmStatus] = useState({ state: "idle", message: "" });
  const [prewarmRevision, setPrewarmRevision] = useState(0);
  const lastPrewarmKeyRef = useRef("");
  const activePrewarmRequestKeyRef = useRef("");
  const prewarmTimerRef = useRef<number | null>(null);
  const prewarmAbortRef = useRef<AbortController | null>(null);

  const triggerPrewarmRefresh = useCallback(() => {
    lastPrewarmKeyRef.current = "";
    setPrewarmRevision((prev) => prev + 1);
  }, []);

  useEffect(() => {
    const plan = buildPrewarmPlan();
    if (!plan) {
      activePrewarmRequestKeyRef.current = "";
      setPrewarmStatus({ state: "idle", message: "" });
      return;
    }

    const prewarmKey = JSON.stringify(plan.keyPayload);
    if (prewarmKey === lastPrewarmKeyRef.current) {
      return;
    }
    activePrewarmRequestKeyRef.current = prewarmKey;

    if (prewarmTimerRef.current !== null) {
      window.clearTimeout(prewarmTimerRef.current);
      prewarmTimerRef.current = null;
    }
    if (prewarmAbortRef.current) {
      prewarmAbortRef.current.abort();
      prewarmAbortRef.current = null;
    }

    prewarmTimerRef.current = window.setTimeout(async () => {
      const controller = new AbortController();
      prewarmAbortRef.current = controller;
      const totalChunks = Array.isArray(plan.chunkPayloads) ? plan.chunkPayloads.length : 0;
      const sleep = (ms: number) =>
        new Promise((resolve) => {
          setTimeout(resolve, ms);
        });
      const isCurrentRequest = () =>
        !controller.signal.aborted && activePrewarmRequestKeyRef.current === prewarmKey;
      const chunkLabel = (chunkPayload: Record<string, any>, index: number) => {
        if (chunkPayload?.prewarm_scope === "range") {
          const from = String(chunkPayload?.date_from || "").trim();
          const to = String(chunkPayload?.date_to || "").trim();
          return `${index + 1}/${totalChunks} ${from}..${to}`;
        }
        return `${index + 1}/${totalChunks} ticker scope`;
      };

      let totalBars = 0;
      let totalReferenceBars = 0;
      let l2CoveredMinutes = 0;
      let anyL2 = false;
      let anyL2Guard = false;
      let finalScope = "range";
      try {
        for (let index = 0; index < totalChunks; index += 1) {
          const chunkPayload = plan.chunkPayloads[index];
          const statusPrefix = `Prewarming cache chunk ${chunkLabel(chunkPayload, index)}...`;
          if (!isCurrentRequest()) return;
          setPrewarmStatus({ state: "warming", message: statusPrefix });

          let statusResp = await fetch("/api/run/prewarm/status", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(chunkPayload),
            signal: controller.signal,
          });
          let statusData = await statusResp.json().catch(() => ({}));
          if (!isCurrentRequest()) return;

          if (statusResp.ok && statusData?.in_progress && !statusData?.ready) {
            for (let poll = 0; poll < 18; poll += 1) {
              await sleep(1000);
              if (!isCurrentRequest()) return;
              statusResp = await fetch("/api/run/prewarm/status", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(chunkPayload),
                signal: controller.signal,
              });
              statusData = await statusResp.json().catch(() => ({}));
              if (statusResp.ok && statusData?.ready) break;
              if (!(statusResp.ok && statusData?.in_progress)) break;
            }
          }

          let result: Record<string, any> | null = null;
          if (statusResp.ok && statusData?.ready) {
            result = { ...statusData, cache_hit: true };
          } else {
            let lastError: any = null;
            for (let attempt = 1; attempt <= chunkMaxRetries; attempt += 1) {
              if (!isCurrentRequest()) return;
              try {
                const resp = await fetch("/api/run/prewarm", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(chunkPayload),
                  signal: controller.signal,
                });
                const data = await resp.json().catch(() => ({}));
                if (!resp.ok) {
                  throw new Error(data?.detail || `HTTP ${resp.status}`);
                }
                result = data;
                break;
              } catch (err) {
                lastError = err;
                if (attempt >= chunkMaxRetries) break;
                setPrewarmStatus({
                  state: "warming",
                  message: `${statusPrefix} retry ${attempt}/${chunkMaxRetries - 1}`,
                });
                await sleep(retryBaseMs * attempt);
              }
            }
            if (!result) {
              throw lastError || new Error("Prewarm request failed");
            }
          }

          totalBars += Number(result?.bars || 0);
          totalReferenceBars += Number(result?.reference_bars || 0);
          l2CoveredMinutes += Number(result?.l2?.covered_minutes || 0);
          anyL2 = anyL2 || !!result?.use_l2;
          anyL2Guard = anyL2Guard || !!result?.l2_guard_reason;
          finalScope = String(result?.prewarm_scope || finalScope || "range").toLowerCase();
        }

        if (!isCurrentRequest()) return;
        lastPrewarmKeyRef.current = prewarmKey;

        if (totalChunks > 1) {
          const summary = {
            bars: totalBars,
            reference_bars: totalReferenceBars,
            use_l2: anyL2,
            l2_guard_reason: anyL2Guard ? "active" : "",
            l2: { covered_minutes: l2CoveredMinutes },
            prewarm_scope: finalScope,
            cache_hit: false,
          };
          setPrewarmStatus({
            state: "ready",
            message: `${formatPrewarmReadyMessage(summary)} | chunks ${totalChunks}`,
          });
          return;
        }

        setPrewarmStatus({
          state: "ready",
          message: formatPrewarmReadyMessage({
            bars: totalBars,
            reference_bars: totalReferenceBars,
            use_l2: anyL2,
            l2_guard_reason: anyL2Guard ? "active" : "",
            l2: { covered_minutes: l2CoveredMinutes },
            prewarm_scope: finalScope,
            cache_hit: false,
          }),
        });
      } catch (err) {
        if (!isCurrentRequest()) return;
        setPrewarmStatus({
          state: "warming",
          message:
            "Prewarm unavailable (network timeout). Run can start now; remaining data will load in background.",
        });
        setTimeout(() => {
          if (activePrewarmRequestKeyRef.current !== prewarmKey) return;
          setPrewarmRevision((prev) => prev + 1);
        }, 1800);
      } finally {
        if (prewarmAbortRef.current === controller) {
          prewarmAbortRef.current = null;
        }
      }
    }, 250);

    return () => {
      if (prewarmTimerRef.current !== null) {
        window.clearTimeout(prewarmTimerRef.current);
        prewarmTimerRef.current = null;
      }
      if (activePrewarmRequestKeyRef.current === prewarmKey) {
        activePrewarmRequestKeyRef.current = "";
      }
    };
  }, [buildPrewarmPlan, chunkMaxRetries, formatPrewarmReadyMessage, prewarmRevision, retryBaseMs]);

  useEffect(() => {
    return () => {
      if (prewarmTimerRef.current !== null) {
        window.clearTimeout(prewarmTimerRef.current);
        prewarmTimerRef.current = null;
      }
      if (prewarmAbortRef.current) {
        prewarmAbortRef.current.abort();
        prewarmAbortRef.current = null;
      }
      activePrewarmRequestKeyRef.current = "";
    };
  }, []);

  return {
    prewarmStatus,
    setPrewarmStatus,
    triggerPrewarmRefresh,
  };
};
