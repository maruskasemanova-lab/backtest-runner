export type CandlestickChartThemeColors = {
  bg: string;
  grid: string;
  text: string;
  up: string;
  down: string;
  wick: string;
  accent: string;
};

export type CandlestickChartMarkerPalette = {
  long: string;
  short: string;
  neutral: string;
  blue: string;
  amber: string;
  ice_buy: string;
  ice_sell: string;
};

export const getCssVar = (name: string, fallback: string): string => {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
};

export const getCandlestickChartThemeColors = (): CandlestickChartThemeColors => ({
  bg: getCssVar("--bg-card", "#ffffff"),
  grid: getCssVar("--border-color", "#e5e7eb"),
  text: getCssVar("--text-secondary", "#6b7280"),
  up: getCssVar("--candle-up", "#0f766e"),
  down: getCssVar("--candle-down", "#dc2626"),
  wick: getCssVar("--candle-wick", "#7c756b"),
  accent: getCssVar("--accent-blue", "#1d4ed8"),
});

export const getCandlestickMarkerPalette = (): CandlestickChartMarkerPalette => ({
  long: getCssVar("--accent-green", "#0f766e"),
  short: getCssVar("--accent-red", "#dc2626"),
  neutral: "#475569",
  blue: getCssVar("--accent-blue", "#1d4ed8"),
  amber: getCssVar("--accent-amber", "#f59e0b"),
  ice_buy: "#00dbe3",
  ice_sell: "#ff00d4",
});
