export type UnifiedConfigSectionId =
  | "strategies"
  | "risk_sizing"
  | "exit_management"
  | "order_flow"
  | "regime_market"
  | "general"
  | "active_profile";

export type UnifiedConfigSection = {
  id: UnifiedConfigSectionId;
  label: string;
  description: string;
  icon: string;
  colorClass: string;
};

export const UNIFIED_CONFIG_SECTIONS: UnifiedConfigSection[] = [
  {
    id: "strategies",
    label: "Strategies & Entry",
    description:
      "Which strategies fire and how sensitive their entry conditions are. Lower thresholds = more signals, higher = fewer but stronger.",
    icon: "\u25B6",
    colorClass: "text-blue-400",
  },
  {
    id: "risk_sizing",
    label: "Risk & Position Sizing",
    description:
      "How much capital is risked per trade, position sizing limits, and stop-loss behavior.",
    icon: "\u26A0",
    colorClass: "text-red-400",
  },
  {
    id: "exit_management",
    label: "Exit Management",
    description:
      "When and how positions get closed: partial take-profit, adverse flow protection, time exit.",
    icon: "\u2716",
    colorClass: "text-orange-400",
  },
  {
    id: "order_flow",
    label: "Order Flow Gates",
    description:
      "Order flow quality filters that must be met before entry: L2, TCBBO, liquidity sweeps, momentum.",
    icon: "\u21C6",
    colorClass: "text-amber-400",
  },
  {
    id: "regime_market",
    label: "Regime & Market",
    description:
      "How market conditions are classified and how they affect trading decisions and risk.",
    icon: "\u2261",
    colorClass: "text-purple-400",
  },
  {
    id: "general",
    label: "General Settings",
    description:
      "Account sizing, intraday level tracking, and micro confirmation configuration.",
    icon: "\u2699",
    colorClass: "text-emerald-400",
  },
  {
    id: "active_profile",
    label: "Active Profile",
    description:
      "Read-only reference of the currently loaded unified profile parameters.",
    icon: "\u2139",
    colorClass: "text-indigo-400",
  },
];

export type SnapshotEntry = {
  key: string;
  kind: "boolean" | "scalar" | "complex";
  boolValue: boolean;
  textValue: string;
  rows: number;
};

export type SnapshotSection = {
  title: string;
  config?: Record<string, any> | null;
  description?: string;
};

export type UnifiedConfigDialogProps = {
  isOpen: boolean;
  onClose: () => void;

  config?: Record<string, any>;
  handleChange?: (field: string, value: any) => void;

  momentumSleeves?: any[];
  onMomentumSleeveChange?: (...args: any[]) => void;
  onAddMomentumSleeve?: (...args: any[]) => void;
  onRemoveMomentumSleeve?: (...args: any[]) => void;

  strategyApiUrl?: string;
  selectedTicker?: string;

  activeProfile?: any;
  activeProfileId?: string;
  activeProfileName?: string;

  readOnly?: boolean;
  title?: string;
  subtitle?: string;
  snapshotSections?: SnapshotSection[];
};
