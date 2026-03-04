type JsonObject = Record<string, unknown>;

interface WebMcpToolDescriptor<TArgs extends JsonObject = JsonObject> {
  name: string;
  description: string;
  inputSchema?: {
    type: "object";
    properties?: Record<string, unknown>;
    required?: string[];
    additionalProperties?: boolean;
  };
  execute: (args: TArgs) => unknown | Promise<unknown>;
}

interface WebMcpModelContext {
  registerTool: (tool: WebMcpToolDescriptor) => void;
  listTools?: () => Array<{ name: string }>;
}

export type WebMcpRuntimeSnapshot = {
  active_view: string;
  active_tab: string;
  selected_ticker: string | null;
  run_key: string | null;
  run_phase: string | null;
  timeframe: string;
  chart_state: { from: number; to: number } | null;
  price_range: Record<string, unknown> | null;
  bars: Array<Record<string, unknown>>;
  displayed_bars: Array<Record<string, unknown>>;
  current_bar: Record<string, unknown> | null;
  decision_events: Array<Record<string, unknown>>;
  selected_marker: Record<string, unknown> | null;
  latest_bar_analysis: Record<string, unknown> | null;
  snapshot_updated_at_utc: string;
};

type WebMcpWindowState = Window & {
  __backtestWebMcpSnapshot?: WebMcpRuntimeSnapshot | null;
};

type NavSectionKey =
  | "backtest"
  | "data_manager"
  | "strategy_analyzer"
  | "adaptive_studio"
  | "adaptive_tuner"
  | "diagnostics"
  | "live_trader";

const NAV_SECTION_LABELS: Record<NavSectionKey, string> = {
  backtest: "Backtest",
  data_manager: "Data Manager",
  strategy_analyzer: "Strategy Analyzer",
  adaptive_studio: "Adaptive Studio",
  adaptive_tuner: "Adaptive Tuner",
  diagnostics: "Diagnostics",
  live_trader: "Live Trader",
};

const TOOL_NAME_SMOKE = "backtest_webmcp_smoke";
const TOOL_NAME_SWITCH_NAV = "backtest_switch_nav";
const TOOL_NAME_GET_CHART_STATE = "backtest_get_chart_state";
const TOOL_NAME_GET_BARS_SLICE = "backtest_get_bars_slice";
const TOOL_NAME_FIND_BAR = "backtest_find_bar";
const TOOL_NAME_READ_STRATEGY_ANALYSIS = "backtest_read_strategy_analysis";
const TOOL_NAME_NAVIGATE_STRATEGY_RUN = "backtest_navigate_strategy_run";
const REGISTRATION_FLAG = "__backtestWebMcpToolsRegistered";
const SNAPSHOT_KEY = "__backtestWebMcpSnapshot";

const normalizeLabel = (value: string): string =>
  value.toLowerCase().replace(/[^a-z0-9]+/g, "");

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const clamp = (value: number, min: number, max: number): number => {
  if (!Number.isFinite(value)) return min;
  if (value < min) return min;
  if (value > max) return max;
  return value;
};

const toFiniteNumber = (value: unknown): number | null => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const toEpochSeconds = (value: unknown): number | null => {
  const numeric = toFiniteNumber(value);
  if (numeric !== null) {
    if (numeric > 1_000_000_000_000) return Math.floor(numeric / 1000);
    return Math.floor(numeric);
  }
  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) return Math.floor(parsed / 1000);
  }
  return null;
};

const toIsoTimestamp = (epochSec: number | null): string | null => {
  if (!Number.isFinite(epochSec ?? Number.NaN)) return null;
  try {
    return new Date((epochSec as number) * 1000).toISOString();
  } catch {
    return null;
  }
};

const normalizeBar = (bar: unknown, index: number) => {
  if (!isRecord(bar)) return null;
  const time = toEpochSeconds(bar.time ?? bar.timestamp);
  const open = toFiniteNumber(bar.open);
  const high = toFiniteNumber(bar.high);
  const low = toFiniteNumber(bar.low);
  const close = toFiniteNumber(bar.close);
  const volume = toFiniteNumber(bar.volume);
  const barIndex = toFiniteNumber(bar.bar_index);
  const placeholder = Boolean(bar.__wfPlaceholder);
  return {
    index,
    bar_index: barIndex !== null ? Math.trunc(barIndex) : null,
    time,
    timestamp_utc: toIsoTimestamp(time),
    open,
    high,
    low,
    close,
    volume,
    placeholder,
  };
};

const normalizeMarker = (marker: unknown, index: number) => {
  if (!isRecord(marker)) return null;
  const time = toEpochSeconds(marker.time ?? marker.timestamp);
  const barIndex = toFiniteNumber(marker.bar_index);
  const price = toFiniteNumber(marker.price);
  return {
    index,
    id: marker.id ?? null,
    marker_type: typeof marker.marker_type === "string" ? marker.marker_type : null,
    strategy: typeof marker.strategy === "string" ? marker.strategy : null,
    regime: typeof marker.regime === "string" ? marker.regime : null,
    side: typeof marker.side === "string" ? marker.side : null,
    price,
    bar_index: barIndex !== null ? Math.trunc(barIndex) : null,
    time,
    timestamp_utc: toIsoTimestamp(time),
    title: typeof marker.title === "string" ? marker.title : null,
    description: typeof marker.description === "string" ? marker.description : null,
  };
};

const readSnapshot = (): WebMcpRuntimeSnapshot | null => {
  if (typeof window === "undefined") return null;
  const runtimeWindow = window as WebMcpWindowState;
  const snapshot = runtimeWindow[SNAPSHOT_KEY];
  if (!snapshot || !isRecord(snapshot)) return null;
  return snapshot as WebMcpRuntimeSnapshot;
};

const readBarsFromSnapshot = (
  snapshot: WebMcpRuntimeSnapshot,
  source: "bars" | "displayed_bars",
): Array<Record<string, unknown>> => {
  const raw = source === "displayed_bars" ? snapshot.displayed_bars : snapshot.bars;
  return Array.isArray(raw) ? raw : [];
};

type StrategyRunNavigationAction =
  | "status"
  | "next"
  | "prev"
  | "start"
  | "end"
  | "set_offset"
  | "set_progress_pct";

type StrategyRunScrubControls = {
  slider: HTMLInputElement;
  prevButton: HTMLButtonElement | null;
  nextButton: HTMLButtonElement | null;
  latestButton: HTMLButtonElement | null;
};

type StrategyRunScrubState = {
  active_view: string | null;
  selected_ticker: string | null;
  run_key: string | null;
  timeframe: string | null;
  current_offset: number;
  min_offset: number;
  max_offset: number;
  step_bars: number;
  can_go_prev: boolean;
  can_go_next: boolean;
  at_start: boolean;
  at_end: boolean;
  snapshot_updated_at_utc: string | null;
};

const waitForUiTick = async (delayMs = 40): Promise<void> =>
  new Promise((resolve) => window.setTimeout(resolve, delayMs));

const findStrategyRunScrubControls = (): StrategyRunScrubControls | null => {
  if (typeof document === "undefined") return null;
  const slider =
    document.querySelector<HTMLInputElement>('input[data-webmcp="strategy-analyzer-scrub-range"]') ||
    document.querySelector<HTMLInputElement>(
      'input[type="range"][aria-label="Navigate walking-forward progress in selected range"]',
    );
  if (!slider) return null;

  const prevButton =
    document.querySelector<HTMLButtonElement>('button[data-webmcp="strategy-analyzer-scrub-prev"]') ||
    Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find((button) =>
      String(button.title || "").toLowerCase().includes("previous executed"),
    ) ||
    null;
  const nextButton =
    document.querySelector<HTMLButtonElement>('button[data-webmcp="strategy-analyzer-scrub-next"]') ||
    Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find((button) =>
      String(button.title || "").toLowerCase().includes("next executed"),
    ) ||
    null;
  const latestButton =
    document.querySelector<HTMLButtonElement>('button[data-webmcp="strategy-analyzer-scrub-latest"]') ||
    Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(
      (button) => normalizeLabel(button.textContent || "") === "latest",
    ) ||
    null;

  return {
    slider,
    prevButton,
    nextButton,
    latestButton,
  };
};

const readStrategyRunScrubState = (
  controls: StrategyRunScrubControls,
  snapshot: WebMcpRuntimeSnapshot | null,
): StrategyRunScrubState => {
  const minRaw = Number(controls.slider.min);
  const minOffset = Number.isFinite(minRaw) ? Math.trunc(minRaw) : 0;
  const maxRaw = Number(controls.slider.max);
  const maxOffset = Number.isFinite(maxRaw) ? Math.max(minOffset, Math.trunc(maxRaw)) : minOffset;
  const stepRaw = Number(controls.slider.step);
  const stepBars = Number.isFinite(stepRaw) && stepRaw > 0 ? Math.max(1, Math.trunc(stepRaw)) : 1;
  const currentRaw = Number(controls.slider.value);
  const currentOffset = clamp(
    Number.isFinite(currentRaw) ? Math.trunc(currentRaw) : minOffset,
    minOffset,
    maxOffset,
  );
  const canGoPrev = controls.prevButton ? !controls.prevButton.disabled : currentOffset > minOffset;
  const canGoNext = controls.nextButton ? !controls.nextButton.disabled : currentOffset < maxOffset;

  return {
    active_view: snapshot?.active_view ?? null,
    selected_ticker: snapshot?.selected_ticker ?? null,
    run_key: snapshot?.run_key ?? null,
    timeframe: snapshot?.timeframe ?? null,
    current_offset: currentOffset,
    min_offset: minOffset,
    max_offset: maxOffset,
    step_bars: stepBars,
    can_go_prev: canGoPrev,
    can_go_next: canGoNext,
    at_start: currentOffset <= minOffset || !canGoPrev,
    at_end: currentOffset >= maxOffset || !canGoNext,
    snapshot_updated_at_utc: snapshot?.snapshot_updated_at_utc ?? null,
  };
};

const setStrategyRunScrubOffset = async (
  controls: StrategyRunScrubControls,
  targetOffset: number,
): Promise<{
  requested_offset: number;
  applied_offset: number;
  moved: boolean;
  state: StrategyRunScrubState;
}> => {
  const beforeSnapshot = readSnapshot();
  const beforeState = readStrategyRunScrubState(controls, beforeSnapshot);
  const requestedOffset = clamp(
    Math.trunc(targetOffset),
    beforeState.min_offset,
    beforeState.max_offset,
  );
  controls.slider.value = String(requestedOffset);
  controls.slider.dispatchEvent(new Event("input", { bubbles: true }));
  controls.slider.dispatchEvent(new Event("change", { bubbles: true }));
  await waitForUiTick();

  const resolvedControls = findStrategyRunScrubControls() || controls;
  const afterSnapshot = readSnapshot();
  const afterState = readStrategyRunScrubState(resolvedControls, afterSnapshot);
  return {
    requested_offset: requestedOffset,
    applied_offset: afterState.current_offset,
    moved: afterState.current_offset !== beforeState.current_offset,
    state: afterState,
  };
};

export const publishWebMcpSnapshot = (snapshot: WebMcpRuntimeSnapshot | null): void => {
  if (typeof window === "undefined") return;
  const runtimeWindow = window as WebMcpWindowState;
  runtimeWindow[SNAPSHOT_KEY] = snapshot;
};

const resolveModelContext = (): WebMcpModelContext | null => {
  if (typeof navigator === "undefined") {
    return null;
  }
  const nav = navigator as Navigator & {
    modelContext?: WebMcpModelContext;
    modelContextTesting?: WebMcpModelContext;
  };
  const context = nav.modelContext ?? nav.modelContextTesting ?? null;
  if (!context || typeof context.registerTool !== "function") {
    return null;
  }
  return context;
};

// Bridge script (polyfill + embed.js) is loaded from index.html.
// No dynamic loading needed.

const registerSmokeTool = (modelContext: WebMcpModelContext, existingTools: Set<string>): void => {
  if (existingTools.has(TOOL_NAME_SMOKE)) {
    return;
  }
  modelContext.registerTool({
    name: TOOL_NAME_SMOKE,
    description: "Lightweight WebMCP health check for Backtest Runner frontend.",
    inputSchema: {
      type: "object",
      properties: {
        message: { type: "string", description: "Optional echo message." },
      },
      additionalProperties: false,
    },
    execute: (args: { message?: string }) => {
      const message = typeof args?.message === "string" ? args.message : "";
      return {
        ok: true,
        echoed_message: message,
        page_url: window.location.href,
        page_title: document.title,
        timestamp_utc: new Date().toISOString(),
      };
    },
  });
};

const registerSwitchNavTool = (
  modelContext: WebMcpModelContext,
  existingTools: Set<string>
): void => {
  if (existingTools.has(TOOL_NAME_SWITCH_NAV)) {
    return;
  }
  modelContext.registerTool({
    name: TOOL_NAME_SWITCH_NAV,
    description: "Switches the main sidebar section in Backtest Runner frontend.",
    inputSchema: {
      type: "object",
      properties: {
        section: {
          type: "string",
          enum: Object.keys(NAV_SECTION_LABELS),
          description: "Target sidebar section key.",
        },
      },
      required: ["section"],
      additionalProperties: false,
    },
    execute: async (args: { section: NavSectionKey }) => {
      const requestedRaw = typeof args?.section === "string" ? args.section : "";
      const requested = normalizeLabel(requestedRaw);
      const sectionKey = (Object.keys(NAV_SECTION_LABELS) as NavSectionKey[]).find(
        (key) => requested === normalizeLabel(key) || requested === normalizeLabel(NAV_SECTION_LABELS[key])
      );
      if (!sectionKey) {
        return {
          ok: false,
          error: "Unknown section value.",
          requested: requestedRaw,
          allowed_sections: Object.keys(NAV_SECTION_LABELS),
        };
      }

      const targetLabel = NAV_SECTION_LABELS[sectionKey];
      const targetToken = normalizeLabel(targetLabel);
      const button = Array.from(document.querySelectorAll("button")).find((candidate) => {
        const text = normalizeLabel(candidate.textContent ?? "");
        return text.includes(targetToken);
      });

      if (!button) {
        return {
          ok: false,
          error: "Navigation button not found in DOM.",
          section: sectionKey,
          label: targetLabel,
        };
      }

      button.click();
      await new Promise((resolve) => window.setTimeout(resolve, 60));

      return {
        ok: true,
        section: sectionKey,
        clicked_label: (button.textContent ?? "").trim(),
        page_url: window.location.href,
      };
    },
  });
};

const registerGetChartStateTool = (
  modelContext: WebMcpModelContext,
  existingTools: Set<string>,
): void => {
  if (existingTools.has(TOOL_NAME_GET_CHART_STATE)) {
    return;
  }
  modelContext.registerTool({
    name: TOOL_NAME_GET_CHART_STATE,
    description:
      "Returns current chart/workspace state including active view, range, ticker, and bar counts.",
    inputSchema: {
      type: "object",
      properties: {},
      additionalProperties: false,
    },
    execute: () => {
      const snapshot = readSnapshot();
      if (!snapshot) {
        return {
          ok: false,
          error: "WebMCP runtime snapshot unavailable.",
        };
      }
      const displayedBars = readBarsFromSnapshot(snapshot, "displayed_bars");
      const normalizedDisplayedBars = displayedBars
        .map((bar, index) => normalizeBar(bar, index))
        .filter((bar): bar is NonNullable<ReturnType<typeof normalizeBar>> => Boolean(bar));
      const rangeFrom = toFiniteNumber(snapshot.chart_state?.from);
      const rangeTo = toFiniteNumber(snapshot.chart_state?.to);
      const visibleBarsInRange =
        rangeFrom !== null && rangeTo !== null
          ? normalizedDisplayedBars.filter((bar) => {
              const barTime = toFiniteNumber(bar.time);
              return barTime !== null && barTime >= rangeFrom && barTime <= rangeTo;
            }).length
          : null;
      return {
        ok: true,
        active_view: snapshot.active_view,
        active_tab: snapshot.active_tab,
        selected_ticker: snapshot.selected_ticker,
        run_key: snapshot.run_key,
        run_phase: snapshot.run_phase,
        timeframe: snapshot.timeframe,
        chart_state: snapshot.chart_state,
        price_range: snapshot.price_range,
        current_bar: snapshot.current_bar,
        bars_count: Array.isArray(snapshot.bars) ? snapshot.bars.length : 0,
        displayed_bars_count: normalizedDisplayedBars.length,
        decision_events_count: Array.isArray(snapshot.decision_events) ? snapshot.decision_events.length : 0,
        visible_bars_in_range: visibleBarsInRange,
        snapshot_updated_at_utc: snapshot.snapshot_updated_at_utc,
      };
    },
  });
};

const registerGetBarsSliceTool = (
  modelContext: WebMcpModelContext,
  existingTools: Set<string>,
): void => {
  if (existingTools.has(TOOL_NAME_GET_BARS_SLICE)) {
    return;
  }
  modelContext.registerTool({
    name: TOOL_NAME_GET_BARS_SLICE,
    description:
      "Returns a filtered slice of bars from raw or displayed chart bars for analysis/debugging.",
    inputSchema: {
      type: "object",
      properties: {
        source: {
          type: "string",
          enum: ["bars", "displayed_bars"],
          description: "Bar source: raw run bars or timeframe-aggregated displayed bars.",
        },
        from_time: {
          type: "number",
          description: "Optional inclusive start time (unix seconds).",
        },
        to_time: {
          type: "number",
          description: "Optional inclusive end time (unix seconds).",
        },
        limit: {
          type: "number",
          description: "Max bars to return (1-2000). Default 200.",
        },
        newest_first: {
          type: "boolean",
          description: "Return newest bars first. Default false (chronological).",
        },
        include_placeholders: {
          type: "boolean",
          description: "Include placeholder whitespace bars. Default false.",
        },
      },
      additionalProperties: false,
    },
    execute: (args: {
      source?: "bars" | "displayed_bars";
      from_time?: number;
      to_time?: number;
      limit?: number;
      newest_first?: boolean;
      include_placeholders?: boolean;
    }) => {
      const snapshot = readSnapshot();
      if (!snapshot) {
        return {
          ok: false,
          error: "WebMCP runtime snapshot unavailable.",
        };
      }
      const source = args?.source === "displayed_bars" ? "displayed_bars" : "bars";
      const fromTime = toEpochSeconds(args?.from_time);
      const toTime = toEpochSeconds(args?.to_time);
      const newestFirst = Boolean(args?.newest_first);
      const includePlaceholders = Boolean(args?.include_placeholders);
      const hasExplicitTimeFilter = fromTime !== null || toTime !== null;
      const limit = clamp(Math.trunc(Number(args?.limit ?? 200)), 1, 2000);

      let normalizedBars = readBarsFromSnapshot(snapshot, source)
        .map((bar, index) => normalizeBar(bar, index))
        .filter((bar): bar is NonNullable<ReturnType<typeof normalizeBar>> => Boolean(bar));

      if (!includePlaceholders) {
        normalizedBars = normalizedBars.filter((bar) => !bar.placeholder);
      }
      normalizedBars = normalizedBars.filter((bar) => {
        const barTime = toFiniteNumber(bar.time);
        if (barTime === null) return false;
        if (fromTime !== null && barTime < fromTime) return false;
        if (toTime !== null && barTime > toTime) return false;
        return true;
      });
      normalizedBars.sort((left, right) => {
        const leftTime = toFiniteNumber(left.time) ?? Number.NEGATIVE_INFINITY;
        const rightTime = toFiniteNumber(right.time) ?? Number.NEGATIVE_INFINITY;
        return leftTime - rightTime;
      });
      if (newestFirst) {
        normalizedBars.reverse();
      } else if (!hasExplicitTimeFilter && normalizedBars.length > limit) {
        normalizedBars = normalizedBars.slice(normalizedBars.length - limit);
      }
      if (normalizedBars.length > limit) {
        normalizedBars = normalizedBars.slice(0, limit);
      }

      return {
        ok: true,
        source,
        returned: normalizedBars.length,
        limit,
        newest_first: newestFirst,
        from_time: fromTime,
        to_time: toTime,
        bars: normalizedBars,
      };
    },
  });
};

const registerFindBarTool = (
  modelContext: WebMcpModelContext,
  existingTools: Set<string>,
): void => {
  if (existingTools.has(TOOL_NAME_FIND_BAR)) {
    return;
  }
  modelContext.registerTool({
    name: TOOL_NAME_FIND_BAR,
    description: "Finds a bar by timestamp (exact or nearest) and returns contextual neighboring bars.",
    inputSchema: {
      type: "object",
      properties: {
        time: {
          type: "number",
          description: "Target time in unix seconds.",
        },
        source: {
          type: "string",
          enum: ["bars", "displayed_bars"],
          description: "Bar source to search. Default 'bars'.",
        },
        mode: {
          type: "string",
          enum: ["exact", "nearest"],
          description: "Match mode. Default 'nearest'.",
        },
        neighbors: {
          type: "number",
          description: "Number of bars to include before/after match (0-20). Default 2.",
        },
      },
      required: ["time"],
      additionalProperties: false,
    },
    execute: (args: {
      time: number;
      source?: "bars" | "displayed_bars";
      mode?: "exact" | "nearest";
      neighbors?: number;
    }) => {
      const snapshot = readSnapshot();
      if (!snapshot) {
        return {
          ok: false,
          error: "WebMCP runtime snapshot unavailable.",
        };
      }
      const source = args?.source === "displayed_bars" ? "displayed_bars" : "bars";
      const targetTime = toEpochSeconds(args?.time);
      if (targetTime === null) {
        return {
          ok: false,
          error: "Invalid 'time' argument; expected unix seconds.",
        };
      }
      const neighbors = clamp(Math.trunc(Number(args?.neighbors ?? 2)), 0, 20);
      const mode = args?.mode === "exact" ? "exact" : "nearest";

      const normalizedBars = readBarsFromSnapshot(snapshot, source)
        .map((bar, index) => normalizeBar(bar, index))
        .filter((bar): bar is NonNullable<ReturnType<typeof normalizeBar>> => Boolean(bar))
        .filter((bar) => toFiniteNumber(bar.time) !== null)
        .sort((left, right) => {
          const leftTime = toFiniteNumber(left.time) ?? Number.NEGATIVE_INFINITY;
          const rightTime = toFiniteNumber(right.time) ?? Number.NEGATIVE_INFINITY;
          return leftTime - rightTime;
        });

      if (!normalizedBars.length) {
        return {
          ok: false,
          error: "No bars available in snapshot.",
          source,
        };
      }

      let matchIndex = -1;
      if (mode === "exact") {
        matchIndex = normalizedBars.findIndex((bar) => toFiniteNumber(bar.time) === targetTime);
      } else {
        let bestDistance = Number.POSITIVE_INFINITY;
        normalizedBars.forEach((bar, index) => {
          const barTime = toFiniteNumber(bar.time);
          if (barTime === null) return;
          const distance = Math.abs(barTime - targetTime);
          if (distance < bestDistance) {
            bestDistance = distance;
            matchIndex = index;
          }
        });
      }

      if (matchIndex < 0 || matchIndex >= normalizedBars.length) {
        return {
          ok: false,
          error: mode === "exact" ? "No exact bar found for time." : "No bar found.",
          source,
          target_time: targetTime,
          mode,
        };
      }

      const matched = normalizedBars[matchIndex];
      const beforeStart = Math.max(0, matchIndex - neighbors);
      const afterEnd = Math.min(normalizedBars.length, matchIndex + neighbors + 1);
      const before = normalizedBars.slice(beforeStart, matchIndex);
      const after = normalizedBars.slice(matchIndex + 1, afterEnd);
      const matchedTime = toFiniteNumber(matched.time);

      return {
        ok: true,
        source,
        mode,
        target_time: targetTime,
        matched_time: matchedTime,
        matched_timestamp_utc: toIsoTimestamp(matchedTime),
        matched_bar: matched,
        time_diff_seconds:
          matchedTime !== null ? Math.abs(matchedTime - targetTime) : null,
        before,
        after,
      };
    },
  });
};

const registerReadStrategyAnalysisTool = (
  modelContext: WebMcpModelContext,
  existingTools: Set<string>,
): void => {
  if (existingTools.has(TOOL_NAME_READ_STRATEGY_ANALYSIS)) {
    return;
  }
  modelContext.registerTool({
    name: TOOL_NAME_READ_STRATEGY_ANALYSIS,
    description:
      "Reads strategy-analysis context from the current UI snapshot (latest analysis, selection, and decision markers).",
    inputSchema: {
      type: "object",
      properties: {
        decision_limit: {
          type: "number",
          description: "How many recent decision markers to return (1-200). Default 25.",
        },
        marker_type: {
          type: "string",
          description: "Optional marker_type filter (e.g. entry_executed).",
        },
        include_latest_bar_analysis: {
          type: "boolean",
          description: "Include latest bar analysis payload. Default true.",
        },
        include_selected_marker: {
          type: "boolean",
          description: "Include selected marker payload. Default true.",
        },
      },
      additionalProperties: false,
    },
    execute: (args: {
      decision_limit?: number;
      marker_type?: string;
      include_latest_bar_analysis?: boolean;
      include_selected_marker?: boolean;
    }) => {
      const snapshot = readSnapshot();
      if (!snapshot) {
        return {
          ok: false,
          error: "WebMCP runtime snapshot unavailable.",
        };
      }
      const decisionLimit = clamp(Math.trunc(Number(args?.decision_limit ?? 25)), 1, 200);
      const markerType = typeof args?.marker_type === "string" ? args.marker_type.trim() : "";
      const includeLatestBarAnalysis = args?.include_latest_bar_analysis !== false;
      const includeSelectedMarker = args?.include_selected_marker !== false;

      const normalizedMarkers = (Array.isArray(snapshot.decision_events) ? snapshot.decision_events : [])
        .map((marker, index) => normalizeMarker(marker, index))
        .filter((marker): marker is NonNullable<ReturnType<typeof normalizeMarker>> => Boolean(marker))
        .filter((marker) =>
          markerType ? String(marker.marker_type || "").trim() === markerType : true,
        )
        .sort((left, right) => {
          const leftTime = toFiniteNumber(left.time) ?? Number.NEGATIVE_INFINITY;
          const rightTime = toFiniteNumber(right.time) ?? Number.NEGATIVE_INFINITY;
          return leftTime - rightTime;
        });
      const tail = normalizedMarkers.slice(Math.max(0, normalizedMarkers.length - decisionLimit));

      return {
        ok: true,
        active_view: snapshot.active_view,
        active_tab: snapshot.active_tab,
        selected_ticker: snapshot.selected_ticker,
        run_key: snapshot.run_key,
        timeframe: snapshot.timeframe,
        strategy_view_active: snapshot.active_view === "strategy-analyzer",
        marker_filter: markerType || null,
        decision_count_total: normalizedMarkers.length,
        decision_count_returned: tail.length,
        decision_events: tail,
        selected_marker: includeSelectedMarker ? snapshot.selected_marker : null,
        latest_bar_analysis: includeLatestBarAnalysis ? snapshot.latest_bar_analysis : null,
        snapshot_updated_at_utc: snapshot.snapshot_updated_at_utc,
      };
    },
  });
};

const registerNavigateStrategyRunTool = (
  modelContext: WebMcpModelContext,
  existingTools: Set<string>,
): void => {
  if (existingTools.has(TOOL_NAME_NAVIGATE_STRATEGY_RUN)) {
    return;
  }
  modelContext.registerTool({
    name: TOOL_NAME_NAVIGATE_STRATEGY_RUN,
    description:
      "Navigates the Strategy Analyzer walking-forward scrub slider (status, next/prev, start/end, offset/percent seek).",
    inputSchema: {
      type: "object",
      properties: {
        action: {
          type: "string",
          enum: ["status", "next", "prev", "start", "end", "set_offset", "set_progress_pct"],
          description: "Navigation action. Default 'status'.",
        },
        steps: {
          type: "number",
          description: "For next/prev: number of slider steps to move (1-500). Default 1.",
        },
        offset: {
          type: "number",
          description: "For set_offset: target absolute scrub offset.",
        },
        progress_pct: {
          type: "number",
          description: "For set_progress_pct: target percentage in range [0, 100].",
        },
      },
      additionalProperties: false,
    },
    execute: async (args: {
      action?: StrategyRunNavigationAction;
      steps?: number;
      offset?: number;
      progress_pct?: number;
    }) => {
      const snapshot = readSnapshot();
      const controls = findStrategyRunScrubControls();
      if (!controls) {
        return {
          ok: false,
          error:
            "Strategy Analyzer scrub slider not found. Open Strategy Analyzer and attach/load a run range first.",
          active_view: snapshot?.active_view ?? null,
          run_key: snapshot?.run_key ?? null,
        };
      }

      const action: StrategyRunNavigationAction = (() => {
        const candidate = String(args?.action || "status").trim();
        if (
          candidate === "status" ||
          candidate === "next" ||
          candidate === "prev" ||
          candidate === "start" ||
          candidate === "end" ||
          candidate === "set_offset" ||
          candidate === "set_progress_pct"
        ) {
          return candidate;
        }
        return "status";
      })();

      const baseState = readStrategyRunScrubState(controls, snapshot);

      if (action === "status") {
        return {
          ok: true,
          action,
          state: baseState,
        };
      }

      if (action === "start") {
        const result = await setStrategyRunScrubOffset(controls, baseState.min_offset);
        return {
          ok: true,
          action,
          ...result,
        };
      }

      if (action === "end") {
        const result = await setStrategyRunScrubOffset(controls, baseState.max_offset);
        return {
          ok: true,
          action,
          ...result,
        };
      }

      if (action === "next" || action === "prev") {
        const stepCount = clamp(Math.trunc(Number(args?.steps ?? 1)), 1, 500);
        const direction = action === "next" ? 1 : -1;
        const targetOffset = baseState.current_offset + direction * stepCount * baseState.step_bars;
        const result = await setStrategyRunScrubOffset(controls, targetOffset);
        return {
          ok: true,
          action,
          steps: stepCount,
          ...result,
        };
      }

      if (action === "set_offset") {
        const parsedOffset = toFiniteNumber(args?.offset);
        if (parsedOffset === null) {
          return {
            ok: false,
            error: "Invalid 'offset' argument.",
            action,
            state: baseState,
          };
        }
        const result = await setStrategyRunScrubOffset(controls, parsedOffset);
        return {
          ok: true,
          action,
          ...result,
        };
      }

      if (action === "set_progress_pct") {
        const parsedPct = toFiniteNumber(args?.progress_pct);
        if (parsedPct === null) {
          return {
            ok: false,
            error: "Invalid 'progress_pct' argument.",
            action,
            state: baseState,
          };
        }
        const pct = clamp(parsedPct, 0, 100);
        const span = Math.max(0, baseState.max_offset - baseState.min_offset);
        const targetOffset = baseState.min_offset + Math.round((span * pct) / 100);
        const result = await setStrategyRunScrubOffset(controls, targetOffset);
        return {
          ok: true,
          action,
          requested_progress_pct: pct,
          ...result,
        };
      }

      return {
        ok: false,
        error: "Unsupported action.",
        action,
        state: baseState,
      };
    },
  });
};

const tryRegisterTools = (): boolean => {
  const modelContext = resolveModelContext();
  if (!modelContext) {
    return false;
  }

  const existingTools = new Set(
    typeof modelContext.listTools === "function"
      ? modelContext.listTools().map((tool) => tool.name)
      : []
  );
  registerSmokeTool(modelContext, existingTools);
  registerSwitchNavTool(modelContext, existingTools);
  registerGetChartStateTool(modelContext, existingTools);
  registerGetBarsSliceTool(modelContext, existingTools);
  registerFindBarTool(modelContext, existingTools);
  registerReadStrategyAnalysisTool(modelContext, existingTools);
  registerNavigateStrategyRunTool(modelContext, existingTools);
  return true;
};

export const initializeWebMcpTools = (): void => {
  if (typeof window === "undefined") {
    return;
  }

  const runtimeWindow = window as WebMcpWindowState & {
    [REGISTRATION_FLAG]?: boolean;
  };
  if (runtimeWindow[REGISTRATION_FLAG]) {
    return;
  }

  if (tryRegisterTools()) {
    runtimeWindow[REGISTRATION_FLAG] = true;
    return;
  }

  let retries = 0;
  const maxRetries = 40;
  const timer = window.setInterval(() => {
    retries += 1;
    if (tryRegisterTools()) {
      runtimeWindow[REGISTRATION_FLAG] = true;
      window.clearInterval(timer);
      return;
    }
    if (retries >= maxRetries) {
      window.clearInterval(timer);
      const hasContext =
        typeof (navigator as Navigator & { modelContext?: unknown }).modelContext !== "undefined" ||
        typeof (navigator as Navigator & { modelContextTesting?: unknown }).modelContextTesting !== "undefined";
      if (hasContext) {
        console.warn("[WebMCP] modelContext found but tools could not be registered.");
      }
    }
  }, 250);
};
