import type {
  AOSMomentumDraft,
  AOSMomentumSleeveDraft,
} from "./aosOptimizationsMomentum";
import { safeArray } from "./aosOptimizationsMomentum";

type Props = {
  momentumDraft: AOSMomentumDraft;
  momentumDirty: boolean;
  momentumSaving: boolean;
  momentumError: string | null;
  momentumNotice: string | null;
  rawConfigSaving: boolean;
  onLoadFromJson: () => void;
  onApplyToJson: () => void;
  onSaveToServer: () => void;
  onMomentumChange: (field: keyof AOSMomentumDraft, value: unknown) => void;
  onSleeveChange: (
    index: number,
    field: keyof AOSMomentumSleeveDraft,
    value: unknown,
  ) => void;
  onAddSleeve: () => void;
  onRemoveSleeve: (index: number) => void;
};

export default function AOSOptimizationsMomentumEditor({
  momentumDraft,
  momentumDirty,
  momentumSaving,
  momentumError,
  momentumNotice,
  rawConfigSaving,
  onLoadFromJson,
  onApplyToJson,
  onSaveToServer,
  onMomentumChange,
  onSleeveChange,
  onAddSleeve,
  onRemoveSleeve,
}: Props) {
  const sleeves = safeArray<AOSMomentumSleeveDraft>(momentumDraft?.sleeves);

  return (
    <div
      style={{
        border: "1px solid var(--border-color)",
        borderRadius: "6px",
        padding: "12px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        background: "var(--bg-secondary)",
      }}
    >
      <div style={{ fontWeight: 700, fontSize: "0.82rem" }}>
        Visual Momentum Diversification
      </div>
      <div style={{ color: "var(--text-muted)", fontSize: "0.76rem" }}>
        Structured editor for <code>adaptive.momentum_diversification</code> with multi-sleeve support.
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
        <button className="btn btn-secondary" onClick={onLoadFromJson} disabled={rawConfigSaving || momentumSaving}>
          Load From JSON
        </button>
        <button className="btn btn-secondary" onClick={onApplyToJson} disabled={rawConfigSaving || momentumSaving}>
          Apply Visual To JSON
        </button>
        <button className="btn btn-primary" onClick={onSaveToServer} disabled={momentumSaving}>
          {momentumSaving ? "Saving visual..." : "Save Visual To Server"}
        </button>
      </div>

      {momentumNotice && (
        <div style={{ color: "var(--accent-green)", fontSize: "0.78rem" }}>
          {momentumNotice}
        </div>
      )}
      {momentumError && (
        <div style={{ color: "var(--accent-red)", fontSize: "0.78rem" }}>
          {momentumError}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "8px",
        }}
      >
        <label className="field-row">
          <span>Enabled</span>
          <input
            type="checkbox"
            checked={!!momentumDraft.enabled}
            onChange={(e) => onMomentumChange("enabled", e.target.checked)}
          />
        </label>
        <label className="field-row">
          <span>Require L2 Coverage</span>
          <input
            type="checkbox"
            checked={!!momentumDraft.require_l2_coverage}
            onChange={(e) => onMomentumChange("require_l2_coverage", e.target.checked)}
          />
        </label>
        <label className="field-row">
          <span>Route Enabled</span>
          <input
            type="checkbox"
            checked={!!momentumDraft.route_enabled}
            onChange={(e) => onMomentumChange("route_enabled", e.target.checked)}
          />
        </label>
        <label className="field-row">
          <span>Route Requires L2</span>
          <input
            type="checkbox"
            checked={!!momentumDraft.route_require_l2_coverage}
            onChange={(e) => onMomentumChange("route_require_l2_coverage", e.target.checked)}
          />
        </label>
        <label className="field-row">
          <span>Fail-Fast Enabled</span>
          <input
            type="checkbox"
            checked={!!momentumDraft.fail_fast_exit_enabled}
            onChange={(e) => onMomentumChange("fail_fast_exit_enabled", e.target.checked)}
          />
        </label>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(185px, 1fr))",
          gap: "10px",
        }}
      >
        <div className="form-group">
          <label>Min Flow Score</label>
          <input
            type="number"
            min="0"
            max="100"
            step="0.5"
            value={momentumDraft.min_flow_score}
            onChange={(e) => onMomentumChange("min_flow_score", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Min Directional Consistency</label>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={momentumDraft.min_directional_consistency}
            onChange={(e) => onMomentumChange("min_directional_consistency", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Min Signed Aggression</label>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={momentumDraft.min_signed_aggression}
            onChange={(e) => onMomentumChange("min_signed_aggression", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Min Imbalance</label>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={momentumDraft.min_imbalance}
            onChange={(e) => onMomentumChange("min_imbalance", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Min CVD (Directional)</label>
          <input
            type="number"
            min="-1000000000"
            max="1000000000"
            step="1"
            value={momentumDraft.min_cvd}
            onChange={(e) => onMomentumChange("min_cvd", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Min Directional Price Change %</label>
          <input
            type="number"
            min="-100"
            max="100"
            step="0.01"
            value={momentumDraft.min_directional_price_change_pct}
            onChange={(e) => onMomentumChange("min_directional_price_change_pct", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Min Price Trend Efficiency</label>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={momentumDraft.min_price_trend_efficiency}
            onChange={(e) => onMomentumChange("min_price_trend_efficiency", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Min Last Bar Body Ratio</label>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={momentumDraft.min_last_bar_body_ratio}
            onChange={(e) => onMomentumChange("min_last_bar_body_ratio", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Min Last Bar Close Location</label>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={momentumDraft.min_last_bar_close_location}
            onChange={(e) => onMomentumChange("min_last_bar_close_location", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Min Delta Acceleration</label>
          <input
            type="number"
            min="-1000000000"
            max="1000000000"
            step="1"
            value={momentumDraft.min_delta_acceleration}
            onChange={(e) => onMomentumChange("min_delta_acceleration", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Min Delta-Price Divergence</label>
          <input
            type="number"
            min="-10"
            max="10"
            step="0.01"
            value={momentumDraft.min_delta_price_divergence}
            onChange={(e) => onMomentumChange("min_delta_price_divergence", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Route Flow Score (Impulse)</label>
          <input
            type="number"
            min="0"
            max="100"
            step="0.5"
            value={momentumDraft.route_flow_score_impulse}
            onChange={(e) => onMomentumChange("route_flow_score_impulse", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Fail-Fast Max Bars</label>
          <input
            type="number"
            min="1"
            max="30"
            step="1"
            value={momentumDraft.fail_fast_max_bars}
            onChange={(e) => onMomentumChange("fail_fast_max_bars", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Fail-Fast Signed Aggression Max</label>
          <input
            type="number"
            min="-1"
            max="0"
            step="0.01"
            value={momentumDraft.fail_fast_signed_aggression_max}
            onChange={(e) => onMomentumChange("fail_fast_signed_aggression_max", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Fail-Fast Book Pressure Max</label>
          <input
            type="number"
            min="-1"
            max="0"
            step="0.01"
            value={momentumDraft.fail_fast_book_pressure_max}
            onChange={(e) => onMomentumChange("fail_fast_book_pressure_max", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label>Fail-Fast Directional Consistency Max</label>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={momentumDraft.fail_fast_directional_consistency_max}
            onChange={(e) =>
              onMomentumChange("fail_fast_directional_consistency_max", Number(e.target.value))
            }
          />
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "10px",
        }}
      >
        <div className="form-group">
          <label>Apply To Strategies (CSV)</label>
          <input
            type="text"
            value={momentumDraft.apply_to_strategies}
            onChange={(e) => onMomentumChange("apply_to_strategies", e.target.value)}
            placeholder="momentum_flow,pullback"
          />
        </div>
        <div className="form-group">
          <label>Allowed Micro Regimes (CSV)</label>
          <input
            type="text"
            value={momentumDraft.allowed_micro_regimes}
            onChange={(e) => onMomentumChange("allowed_micro_regimes", e.target.value)}
            placeholder="TRENDING_UP,BREAKOUT"
          />
        </div>
        <div className="form-group">
          <label>Blocked Micro Regimes (CSV)</label>
          <input
            type="text"
            value={momentumDraft.blocked_micro_regimes}
            onChange={(e) => onMomentumChange("blocked_micro_regimes", e.target.value)}
            placeholder="CHOPPY,ABSORPTION"
          />
        </div>
      </div>

      <div
        style={{
          border: "1px solid var(--border-color)",
          borderRadius: "6px",
          padding: "10px",
          background: "var(--bg-primary)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "8px",
          }}
        >
          <div style={{ fontWeight: 700, fontSize: "0.78rem" }}>Momentum Sleeves</div>
          <button className="btn btn-secondary" type="button" onClick={onAddSleeve}>
            Add Sleeve
          </button>
        </div>

        {sleeves.length === 0 ? (
          <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
            No sleeves defined. Add sleeve rows to enable multi-sleeve behavior.
          </div>
        ) : (
          <div style={{ display: "grid", gap: "10px" }}>
            {sleeves.map((sleeve, index) => (
              <div
                key={`${sleeve?.sleeve_id || "sleeve"}-${index}`}
                style={{
                  border: "1px solid var(--border-color)",
                  borderRadius: "6px",
                  padding: "10px",
                  background: "var(--bg-secondary)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "8px",
                  }}
                >
                  <div style={{ fontWeight: 700, fontSize: "0.76rem" }}>Sleeve #{index + 1}</div>
                  <button className="btn btn-secondary" type="button" onClick={() => onRemoveSleeve(index)}>
                    Remove
                  </button>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
                    gap: "8px",
                  }}
                >
                  <div className="form-group">
                    <label>Sleeve ID</label>
                    <input
                      type="text"
                      value={sleeve?.sleeve_id || ""}
                      onChange={(e) => onSleeveChange(index, "sleeve_id", e.target.value)}
                      placeholder="impulse"
                    />
                  </div>
                  <div className="form-group">
                    <label>Allocation Weight (0-1)</label>
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.05"
                      value={sleeve?.allocation_weight ?? 0.5}
                      onChange={(e) => onSleeveChange(index, "allocation_weight", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Apply To Strategies (CSV)</label>
                    <input
                      type="text"
                      value={sleeve?.apply_to_strategies || ""}
                      onChange={(e) => onSleeveChange(index, "apply_to_strategies", e.target.value)}
                      placeholder="momentum_flow,pullback"
                    />
                  </div>
                  <div className="form-group">
                    <label>Allowed Micro Regimes (CSV)</label>
                    <input
                      type="text"
                      value={sleeve?.allowed_micro_regimes || ""}
                      onChange={(e) => onSleeveChange(index, "allowed_micro_regimes", e.target.value)}
                      placeholder="TRENDING_UP,BREAKOUT"
                    />
                  </div>
                  <div className="form-group">
                    <label>Blocked Micro Regimes (CSV)</label>
                    <input
                      type="text"
                      value={sleeve?.blocked_micro_regimes || ""}
                      onChange={(e) => onSleeveChange(index, "blocked_micro_regimes", e.target.value)}
                      placeholder="CHOPPY,ABSORPTION"
                    />
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
                    gap: "8px",
                    marginBottom: "8px",
                  }}
                >
                  <label className="field-row">
                    <span>Enabled</span>
                    <input
                      type="checkbox"
                      checked={!!sleeve?.enabled}
                      onChange={(e) => onSleeveChange(index, "enabled", e.target.checked)}
                    />
                  </label>
                  <label className="field-row">
                    <span>Require L2 Coverage</span>
                    <input
                      type="checkbox"
                      checked={!!sleeve?.require_l2_coverage}
                      onChange={(e) => onSleeveChange(index, "require_l2_coverage", e.target.checked)}
                    />
                  </label>
                  <label className="field-row">
                    <span>Route Enabled</span>
                    <input
                      type="checkbox"
                      checked={!!sleeve?.route_enabled}
                      onChange={(e) => onSleeveChange(index, "route_enabled", e.target.checked)}
                    />
                  </label>
                  <label className="field-row">
                    <span>Route Requires L2</span>
                    <input
                      type="checkbox"
                      checked={!!sleeve?.route_require_l2_coverage}
                      onChange={(e) => onSleeveChange(index, "route_require_l2_coverage", e.target.checked)}
                    />
                  </label>
                  <label className="field-row">
                    <span>Fail-Fast Enabled</span>
                    <input
                      type="checkbox"
                      checked={!!sleeve?.fail_fast_exit_enabled}
                      onChange={(e) => onSleeveChange(index, "fail_fast_exit_enabled", e.target.checked)}
                    />
                  </label>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(175px, 1fr))",
                    gap: "8px",
                  }}
                >
                  <div className="form-group">
                    <label>Min Flow Score</label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={sleeve?.min_flow_score ?? 58}
                      onChange={(e) => onSleeveChange(index, "min_flow_score", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Min Directional Consistency</label>
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={sleeve?.min_directional_consistency ?? 0.45}
                      onChange={(e) => onSleeveChange(index, "min_directional_consistency", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Min Signed Aggression</label>
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={sleeve?.min_signed_aggression ?? 0.04}
                      onChange={(e) => onSleeveChange(index, "min_signed_aggression", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Min Imbalance</label>
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={sleeve?.min_imbalance ?? 0.02}
                      onChange={(e) => onSleeveChange(index, "min_imbalance", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Min CVD (Directional)</label>
                    <input
                      type="number"
                      min="-1000000000"
                      max="1000000000"
                      step="1"
                      value={sleeve?.min_cvd ?? 0}
                      onChange={(e) => onSleeveChange(index, "min_cvd", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Min Directional Price Change %</label>
                    <input
                      type="number"
                      min="-100"
                      max="100"
                      step="0.01"
                      value={sleeve?.min_directional_price_change_pct ?? 0}
                      onChange={(e) => onSleeveChange(index, "min_directional_price_change_pct", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Min Price Trend Efficiency</label>
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={sleeve?.min_price_trend_efficiency ?? 0}
                      onChange={(e) => onSleeveChange(index, "min_price_trend_efficiency", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Min Last Bar Body Ratio</label>
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={sleeve?.min_last_bar_body_ratio ?? 0}
                      onChange={(e) => onSleeveChange(index, "min_last_bar_body_ratio", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Min Last Bar Close Location</label>
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={sleeve?.min_last_bar_close_location ?? 0}
                      onChange={(e) => onSleeveChange(index, "min_last_bar_close_location", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Min Delta Acceleration</label>
                    <input
                      type="number"
                      min="-1000000000"
                      max="1000000000"
                      step="1"
                      value={sleeve?.min_delta_acceleration ?? 0}
                      onChange={(e) => onSleeveChange(index, "min_delta_acceleration", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Min Delta-Price Divergence</label>
                    <input
                      type="number"
                      min="-10"
                      max="10"
                      step="0.01"
                      value={sleeve?.min_delta_price_divergence ?? 0}
                      onChange={(e) => onSleeveChange(index, "min_delta_price_divergence", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Route Flow Score (Impulse)</label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={sleeve?.route_flow_score_impulse ?? 64}
                      onChange={(e) => onSleeveChange(index, "route_flow_score_impulse", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Fail-Fast Max Bars</label>
                    <input
                      type="number"
                      min="1"
                      max="30"
                      step="1"
                      value={sleeve?.fail_fast_max_bars ?? 3}
                      onChange={(e) => onSleeveChange(index, "fail_fast_max_bars", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Fail-Fast Signed Aggression Max</label>
                    <input
                      type="number"
                      min="-1"
                      max="0"
                      step="0.01"
                      value={sleeve?.fail_fast_signed_aggression_max ?? -0.08}
                      onChange={(e) => onSleeveChange(index, "fail_fast_signed_aggression_max", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Fail-Fast Book Pressure Max</label>
                    <input
                      type="number"
                      min="-1"
                      max="0"
                      step="0.01"
                      value={sleeve?.fail_fast_book_pressure_max ?? -0.1}
                      onChange={(e) => onSleeveChange(index, "fail_fast_book_pressure_max", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label>Fail-Fast Directional Consistency Max</label>
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={sleeve?.fail_fast_directional_consistency_max ?? 0.2}
                      onChange={(e) =>
                        onSleeveChange(
                          index,
                          "fail_fast_directional_consistency_max",
                          Number(e.target.value),
                        )
                      }
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {momentumDirty && (
        <div style={{ color: "var(--accent-yellow)", fontSize: "0.76rem" }}>
          Visual momentum editor has unsaved changes.
        </div>
      )}
    </div>
  );
}
