import React, { useEffect, useState } from "react";
import { defaultStrategyApiUrl } from "../../utils";

interface AosHistoryEntry {
  timestamp: string;
  ticker: string;
  old_active_unified_profile_id: string | null;
  new_active_unified_profile_id: string | null;
  old_active_adaptive_tuner_profile_id: string | null;
  new_active_adaptive_tuner_profile_id: string | null;
  active_profile_snapshot: any;
}

export const AosHistoryTimeline: React.FC<{ ticker: string }> = ({ ticker }) => {
  const [history, setHistory] = useState<AosHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchHistory = async () => {
      if (!ticker) {
        setHistory([]);
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${defaultStrategyApiUrl}/api/aos-history/${ticker}`);
        if (!res.ok) {
          throw new Error(`Failed to fetch history: ${res.statusText}`);
        }
        const data = await res.json();
        if (mounted) {
          // Reverse to show newest first
          setHistory(Array.isArray(data) ? data.reverse() : []);
        }
      } catch (e: any) {
        if (mounted) {
          setError(e.message);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    fetchHistory();
    return () => { mounted = false; };
  }, [ticker]);

  if (loading) {
    return <div className="p-4 text-xs text-slate-400">Loading AOS Param History...</div>;
  }

  if (error) {
    return <div className="p-4 text-xs text-red-400">Error: {error}</div>;
  }

  if (history.length === 0) {
    return (
      <div className="p-4 text-xs text-slate-400 border border-slate-700/50 rounded-lg bg-slate-800/20 italic">
        No parameter tuning history recorded for {ticker} yet.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 mt-4">
      <h3 className="text-sm font-semibold text-slate-200">Parameter Evolution Timeline ({ticker})</h3>
      <div className="relative border-l border-slate-700 ml-3 pl-4 pb-2">
        {history.map((entry, idx) => {
          const date = new Date(entry.timestamp);
          const timeStr = date.toLocaleString();
          
          return (
            <div key={idx} className="relative mb-6">
              {/* Timeline marker */}
              <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-blue-500 border-2 border-slate-900" />
              
              <div className="flex flex-col gap-1 p-3 rounded bg-slate-800/50 border border-slate-700/50">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-300">{timeStr}</span>
                  <span className="text-slate-400 font-mono text-[10px]">
                    Unified ID: {entry.new_active_unified_profile_id || "None"}
                  </span>
                </div>
                
                {entry.old_active_unified_profile_id !== entry.new_active_unified_profile_id && (
                  <div className="text-[11px] text-fuchsia-400">
                    Base Profile changed: <span className="text-slate-400 line-through mr-1">{entry.old_active_unified_profile_id || "None"}</span> 
                    → <span className="text-fuchsia-300 font-mono">{entry.new_active_unified_profile_id || "None"}</span>
                  </div>
                )}

                {entry.old_active_adaptive_tuner_profile_id !== entry.new_active_adaptive_tuner_profile_id && (
                  <div className="text-[11px] text-teal-400">
                    Adaptive Tuner changed: <span className="text-slate-400 line-through mr-1">{entry.old_active_adaptive_tuner_profile_id || "None"}</span> 
                    → <span className="text-teal-300 font-mono">{entry.new_active_adaptive_tuner_profile_id || "None"}</span>
                  </div>
                )}
                
                {/* Expandable snapshot diffs could go here if we tracked granular param changes in the backend */}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
