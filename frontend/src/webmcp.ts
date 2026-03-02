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

type WebMcpWindowState = Window & {
  __mcp_b_transports?: unknown;
  __backtestWebMcpBridgeLoadAttempted?: boolean;
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
const REGISTRATION_FLAG = "__backtestWebMcpToolsRegistered";
const MCP_BRIDGE_URL = "https://unpkg.com/@mcp-b/global@latest/dist/index.iife.js";

const normalizeLabel = (value: string): string =>
  value.toLowerCase().replace(/[^a-z0-9]+/g, "");

const resolveModelContext = (): WebMcpModelContext | null => {
  if (typeof navigator === "undefined") {
    return null;
  }
  const context = (navigator as Navigator & { modelContext?: WebMcpModelContext })
    .modelContext;
  if (!context || typeof context.registerTool !== "function") {
    return null;
  }
  return context;
};

const maybeLoadBridgeScript = (): void => {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return;
  }
  const runtimeWindow = window as WebMcpWindowState;
  if (runtimeWindow.__backtestWebMcpBridgeLoadAttempted) {
    return;
  }
  // The bridge expects transport globals to be present; skip in regular browsers.
  if (!runtimeWindow.__mcp_b_transports) {
    return;
  }

  runtimeWindow.__backtestWebMcpBridgeLoadAttempted = true;
  const script = document.createElement("script");
  script.src = MCP_BRIDGE_URL;
  script.async = true;
  script.referrerPolicy = "no-referrer";
  script.onerror = () => {
    console.warn("[WebMCP] Failed to load MCP bridge script.");
  };
  document.head.appendChild(script);
};

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

  maybeLoadBridgeScript();

  if (tryRegisterTools()) {
    runtimeWindow[REGISTRATION_FLAG] = true;
    return;
  }

  let retries = 0;
  const maxRetries = 40;
  const timer = window.setInterval(() => {
    maybeLoadBridgeScript();
    retries += 1;
    if (tryRegisterTools()) {
      runtimeWindow[REGISTRATION_FLAG] = true;
      window.clearInterval(timer);
      return;
    }
    if (retries >= maxRetries) {
      window.clearInterval(timer);
      const shouldReport =
        Boolean(runtimeWindow.__mcp_b_transports) ||
        typeof (navigator as Navigator & { modelContext?: unknown }).modelContext !== "undefined";
      if (shouldReport) {
        console.warn("[WebMCP] modelContext unavailable; tools were not registered.");
      }
    }
  }, 250);
};
