import type { MomentumConfigSlice, MomentumSleeveDraft } from "./momentumUtils";

interface MomentumDiversificationEditorProps {
  config: MomentumConfigSlice;
  momentumSleeves: MomentumSleeveDraft[];
  onChange: (field: string, value: unknown) => void;
  onMomentumSleeveChange: (
    index: number,
    field: keyof MomentumSleeveDraft,
    value: unknown,
  ) => void;
  onAddMomentumSleeve: () => void;
  onRemoveMomentumSleeve: (index: number) => void;
}

function MomentumDiversificationEditor({
  config,
  momentumSleeves,
  onChange,
  onMomentumSleeveChange,
  onAddMomentumSleeve,
  onRemoveMomentumSleeve,
}: MomentumDiversificationEditorProps) {
  return (
    <div className="tw-panel">
      <div className="tw-panel-title">Momentum Diversification Override</div>
      <div className="tw-panel-hint">
        Voliteľný run-level override pre adaptive momentum routing (L2/CVD +
        price-action prahy, route a fail-fast). Keď je vypnutý, použije sa
        aktívny Adaptive Profile/AOS config.
      </div>

      <div className="form-group">
        <label
          className="field-row"
          htmlFor="momentum_diversification_override_enabled"
        >
          <span>Enable per-run momentum diversification override</span>
          <input
            id="momentum_diversification_override_enabled"
            type="checkbox"
            checked={!!config.momentum_diversification_override_enabled}
            onChange={(e) =>
              onChange(
                "momentum_diversification_override_enabled",
                e.target.checked,
              )
            }
          />
        </label>
      </div>

      {config.momentum_diversification_override_enabled ? (
        <>
          <div className="tw-grid-fit-220 tw-mb-sm">
            <label className="field-row">
              <span>Momentum Diversification Enabled</span>
              <input
                type="checkbox"
                checked={!!config.momentum_diversification_enabled}
                onChange={(e) =>
                  onChange("momentum_diversification_enabled", e.target.checked)
                }
              />
            </label>
            <label className="field-row">
              <span>Require L2 Coverage</span>
              <input
                type="checkbox"
                checked={!!config.momentum_require_l2_coverage}
                onChange={(e) =>
                  onChange("momentum_require_l2_coverage", e.target.checked)
                }
              />
            </label>
            <label className="field-row">
              <span>Route Enabled</span>
              <input
                type="checkbox"
                checked={!!config.momentum_route_enabled}
                onChange={(e) => onChange("momentum_route_enabled", e.target.checked)}
              />
            </label>
            <label className="field-row">
              <span>Route Requires L2 Coverage</span>
              <input
                type="checkbox"
                checked={!!config.momentum_route_require_l2_coverage}
                onChange={(e) =>
                  onChange("momentum_route_require_l2_coverage", e.target.checked)
                }
              />
            </label>
            <label className="field-row">
              <span>Fail-Fast Exit Enabled</span>
              <input
                type="checkbox"
                checked={!!config.momentum_fail_fast_exit_enabled}
                onChange={(e) =>
                  onChange("momentum_fail_fast_exit_enabled", e.target.checked)
                }
              />
            </label>
          </div>

          <div className="tw-grid-fit-190">
            <div className="form-group">
              <label htmlFor="momentum_min_flow_score">Min Flow Score</label>
              <input
                id="momentum_min_flow_score"
                type="number"
                min="0"
                max="100"
                step="0.5"
                value={config.momentum_min_flow_score}
                onChange={(e) =>
                  onChange("momentum_min_flow_score", Number(e.target.value))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_min_directional_consistency">
                Min Directional Consistency
              </label>
              <input
                id="momentum_min_directional_consistency"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={config.momentum_min_directional_consistency}
                onChange={(e) =>
                  onChange(
                    "momentum_min_directional_consistency",
                    Number(e.target.value),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_min_signed_aggression">
                Min Signed Aggression
              </label>
              <input
                id="momentum_min_signed_aggression"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={config.momentum_min_signed_aggression}
                onChange={(e) =>
                  onChange("momentum_min_signed_aggression", Number(e.target.value))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_min_imbalance">Min Imbalance</label>
              <input
                id="momentum_min_imbalance"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={config.momentum_min_imbalance}
                onChange={(e) =>
                  onChange("momentum_min_imbalance", Number(e.target.value))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_min_cvd">Min CVD (Directional)</label>
              <input
                id="momentum_min_cvd"
                type="number"
                min="-1000000000"
                max="1000000000"
                step="1"
                value={config.momentum_min_cvd}
                onChange={(e) => onChange("momentum_min_cvd", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_min_directional_price_change_pct">
                Min Directional Price Change %
              </label>
              <input
                id="momentum_min_directional_price_change_pct"
                type="number"
                min="-100"
                max="100"
                step="0.01"
                value={config.momentum_min_directional_price_change_pct}
                onChange={(e) =>
                  onChange(
                    "momentum_min_directional_price_change_pct",
                    Number(e.target.value),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_min_price_trend_efficiency">
                Min Price Trend Efficiency
              </label>
              <input
                id="momentum_min_price_trend_efficiency"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={config.momentum_min_price_trend_efficiency}
                onChange={(e) =>
                  onChange(
                    "momentum_min_price_trend_efficiency",
                    Number(e.target.value),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_min_last_bar_body_ratio">
                Min Last Bar Body Ratio
              </label>
              <input
                id="momentum_min_last_bar_body_ratio"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={config.momentum_min_last_bar_body_ratio}
                onChange={(e) =>
                  onChange("momentum_min_last_bar_body_ratio", Number(e.target.value))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_min_last_bar_close_location">
                Min Last Bar Close Location
              </label>
              <input
                id="momentum_min_last_bar_close_location"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={config.momentum_min_last_bar_close_location}
                onChange={(e) =>
                  onChange(
                    "momentum_min_last_bar_close_location",
                    Number(e.target.value),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_min_delta_acceleration">
                Min Delta Acceleration
              </label>
              <input
                id="momentum_min_delta_acceleration"
                type="number"
                min="-1000000000"
                max="1000000000"
                step="1"
                value={config.momentum_min_delta_acceleration}
                onChange={(e) =>
                  onChange("momentum_min_delta_acceleration", Number(e.target.value))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_min_delta_price_divergence">
                Min Delta-Price Divergence
              </label>
              <input
                id="momentum_min_delta_price_divergence"
                type="number"
                min="-10"
                max="10"
                step="0.01"
                value={config.momentum_min_delta_price_divergence}
                onChange={(e) =>
                  onChange(
                    "momentum_min_delta_price_divergence",
                    Number(e.target.value),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_route_flow_score_impulse">
                Route Flow Score (Impulse)
              </label>
              <input
                id="momentum_route_flow_score_impulse"
                type="number"
                min="0"
                max="100"
                step="0.5"
                value={config.momentum_route_flow_score_impulse}
                onChange={(e) =>
                  onChange("momentum_route_flow_score_impulse", Number(e.target.value))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_fail_fast_max_bars">Fail-Fast Max Bars</label>
              <input
                id="momentum_fail_fast_max_bars"
                type="number"
                min="1"
                max="30"
                step="1"
                value={config.momentum_fail_fast_max_bars}
                onChange={(e) =>
                  onChange(
                    "momentum_fail_fast_max_bars",
                    Math.max(1, Math.trunc(Number(e.target.value))),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_fail_fast_signed_aggression_max">
                Fail-Fast Signed Aggression Max
              </label>
              <input
                id="momentum_fail_fast_signed_aggression_max"
                type="number"
                min="-1"
                max="0"
                step="0.01"
                value={config.momentum_fail_fast_signed_aggression_max}
                onChange={(e) =>
                  onChange(
                    "momentum_fail_fast_signed_aggression_max",
                    Number(e.target.value),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_fail_fast_book_pressure_max">
                Fail-Fast Book Pressure Max
              </label>
              <input
                id="momentum_fail_fast_book_pressure_max"
                type="number"
                min="-1"
                max="0"
                step="0.01"
                value={config.momentum_fail_fast_book_pressure_max}
                onChange={(e) =>
                  onChange(
                    "momentum_fail_fast_book_pressure_max",
                    Number(e.target.value),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_fail_fast_directional_consistency_max">
                Fail-Fast Directional Consistency Max
              </label>
              <input
                id="momentum_fail_fast_directional_consistency_max"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={config.momentum_fail_fast_directional_consistency_max}
                onChange={(e) =>
                  onChange(
                    "momentum_fail_fast_directional_consistency_max",
                    Number(e.target.value),
                  )
                }
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="momentum_apply_to_strategies">
              Apply To Strategies (CSV, optional)
            </label>
            <input
              id="momentum_apply_to_strategies"
              type="text"
              value={config.momentum_apply_to_strategies ?? ""}
              onChange={(e) =>
                onChange("momentum_apply_to_strategies", e.target.value)
              }
              placeholder="momentum_flow,momentum"
            />
          </div>

          <div className="tw-grid-fit-220">
            <div className="form-group">
              <label htmlFor="momentum_allowed_micro_regimes">
                Allowed Micro Regimes (CSV)
              </label>
              <input
                id="momentum_allowed_micro_regimes"
                type="text"
                value={config.momentum_allowed_micro_regimes ?? ""}
                onChange={(e) =>
                  onChange("momentum_allowed_micro_regimes", e.target.value)
                }
                placeholder="TRENDING_UP,BREAKOUT"
              />
            </div>
            <div className="form-group">
              <label htmlFor="momentum_blocked_micro_regimes">
                Blocked Micro Regimes (CSV)
              </label>
              <input
                id="momentum_blocked_micro_regimes"
                type="text"
                value={config.momentum_blocked_micro_regimes ?? ""}
                onChange={(e) =>
                  onChange("momentum_blocked_micro_regimes", e.target.value)
                }
                placeholder="CHOPPY,ABSORPTION"
              />
            </div>
          </div>

          <div className="tw-subpanel">
            <div className="tw-subpanel-header">
              <div className="tw-subpanel-title">Multi-Sleeve Diversification</div>
              <button
                type="button"
                className="btn btn-secondary tw-btn-compact"
                onClick={onAddMomentumSleeve}
              >
                Add Sleeve
              </button>
            </div>
            <div className="tw-subpanel-copy">
              Vizualny editor pre `sleeves[]`. Ak pridáš aspoň jeden sleeve,
              backend použije multi-sleeve režim.
            </div>

            {momentumSleeves.length === 0 ? (
              <div className="text-[0.75rem] text-app-text-muted">
                Zatial nie je definovany ziadny sleeve.
              </div>
            ) : (
              <div className="tw-sleeves-grid">
                {momentumSleeves.map((sleeve, index) => (
                  <div key={`${sleeve?.sleeve_id || "sleeve"}-${index}`} className="tw-sleeve-card">
                    <div className="tw-sleeve-header">
                      <div className="tw-sleeve-title">Sleeve #{index + 1}</div>
                      <button
                        type="button"
                        className="btn btn-secondary tw-btn-compact-xs"
                        onClick={() => onRemoveMomentumSleeve(index)}
                      >
                        Remove
                      </button>
                    </div>

                    <div className="tw-grid-fit-200">
                      <div className="form-group">
                        <label>Sleeve ID</label>
                        <input
                          type="text"
                          value={sleeve?.sleeve_id || ""}
                          onChange={(e) =>
                            onMomentumSleeveChange(index, "sleeve_id", e.target.value)
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "allocation_weight",
                              Number(e.target.value),
                            )
                          }
                        />
                      </div>
                      <div className="form-group">
                        <label>Apply To Strategies (CSV)</label>
                        <input
                          type="text"
                          value={sleeve?.apply_to_strategies || ""}
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "apply_to_strategies",
                              e.target.value,
                            )
                          }
                          placeholder="momentum_flow,pullback"
                        />
                      </div>
                      <div className="form-group">
                        <label>Allowed Micro Regimes (CSV)</label>
                        <input
                          type="text"
                          value={sleeve?.allowed_micro_regimes || ""}
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "allowed_micro_regimes",
                              e.target.value,
                            )
                          }
                          placeholder="TRENDING_UP,BREAKOUT"
                        />
                      </div>
                      <div className="form-group">
                        <label>Blocked Micro Regimes (CSV)</label>
                        <input
                          type="text"
                          value={sleeve?.blocked_micro_regimes || ""}
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "blocked_micro_regimes",
                              e.target.value,
                            )
                          }
                          placeholder="CHOPPY,ABSORPTION"
                        />
                      </div>
                    </div>

                    <div className="tw-grid-fit-220 tw-mb-sm">
                      <label className="field-row">
                        <span>Enabled</span>
                        <input
                          type="checkbox"
                          checked={!!sleeve?.enabled}
                          onChange={(e) =>
                            onMomentumSleeveChange(index, "enabled", e.target.checked)
                          }
                        />
                      </label>
                      <label className="field-row">
                        <span>Require L2 Coverage</span>
                        <input
                          type="checkbox"
                          checked={!!sleeve?.require_l2_coverage}
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "require_l2_coverage",
                              e.target.checked,
                            )
                          }
                        />
                      </label>
                      <label className="field-row">
                        <span>Route Enabled</span>
                        <input
                          type="checkbox"
                          checked={!!sleeve?.route_enabled}
                          onChange={(e) =>
                            onMomentumSleeveChange(index, "route_enabled", e.target.checked)
                          }
                        />
                      </label>
                      <label className="field-row">
                        <span>Route Requires L2</span>
                        <input
                          type="checkbox"
                          checked={!!sleeve?.route_require_l2_coverage}
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "route_require_l2_coverage",
                              e.target.checked,
                            )
                          }
                        />
                      </label>
                      <label className="field-row">
                        <span>Fail-Fast Exit Enabled</span>
                        <input
                          type="checkbox"
                          checked={!!sleeve?.fail_fast_exit_enabled}
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "fail_fast_exit_enabled",
                              e.target.checked,
                            )
                          }
                        />
                      </label>
                    </div>

                    <div className="tw-grid-fit-185">
                      <div className="form-group">
                        <label>Min Flow Score</label>
                        <input
                          type="number"
                          min="0"
                          max="100"
                          step="0.5"
                          value={sleeve?.min_flow_score ?? 58}
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "min_flow_score",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "min_directional_consistency",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "min_signed_aggression",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "min_imbalance",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(index, "min_cvd", Number(e.target.value))
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "min_directional_price_change_pct",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "min_price_trend_efficiency",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "min_last_bar_body_ratio",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "min_last_bar_close_location",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "min_delta_acceleration",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "min_delta_price_divergence",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "route_flow_score_impulse",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "fail_fast_max_bars",
                              Math.max(1, Math.trunc(Number(e.target.value))),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "fail_fast_signed_aggression_max",
                              Number(e.target.value),
                            )
                          }
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
                          onChange={(e) =>
                            onMomentumSleeveChange(
                              index,
                              "fail_fast_book_pressure_max",
                              Number(e.target.value),
                            )
                          }
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
                            onMomentumSleeveChange(
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
        </>
      ) : (
        <div className="text-[0.78rem] text-app-text-muted">
          Override je vypnutý, použije sa profil z Adaptive Tuner/AOS.
        </div>
      )}
    </div>
  );
}

export default MomentumDiversificationEditor;
