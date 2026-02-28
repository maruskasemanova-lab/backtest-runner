type FootprintChartToolbarProps = {
  showCVD: boolean;
  onToggleCvd: () => void;
  onToggleFullscreen: () => void;
};

const CONTROL_ROW_STYLE = {
  position: "absolute",
  top: "10px",
  right: "60px",
  zIndex: 20,
  display: "flex",
  gap: "8px",
} as const;

const BASE_BUTTON_STYLE = {
  border: "1px solid rgba(255, 255, 255, 0.2)",
  color: "#fff",
  borderRadius: "4px",
  padding: "4px 8px",
  cursor: "pointer",
} as const;

function FootprintChartToolbar({
  showCVD,
  onToggleCvd,
  onToggleFullscreen,
}: FootprintChartToolbarProps) {
  return (
    <div style={CONTROL_ROW_STYLE}>
      <button
        onClick={onToggleCvd}
        style={{
          ...BASE_BUTTON_STYLE,
          background: showCVD ? "rgba(38, 166, 154, 0.6)" : "rgba(255, 255, 255, 0.1)",
          fontSize: "12px",
          fontWeight: "bold",
        }}
        title="Toggle Accum. Delta (CVD)"
      >
        CVD
      </button>
      <button
        onClick={onToggleFullscreen}
        style={{
          ...BASE_BUTTON_STYLE,
          background: "rgba(255, 255, 255, 0.1)",
          fontSize: "16px",
        }}
        title="Toggle Fullscreen"
      >
        ⛶
      </button>
    </div>
  );
}

export default FootprintChartToolbar;
