type Props = {
  l2BranchSummary: string;
  noL2BranchSummary: string;
  activeUnifiedId: string;
  legacyComboSourceId: string;
  legacyTunedSourceId: string;
  hysteresisBars: number;
  cooldownBars: number;
  strategyModeLabel: string;
};

export default function AdaptiveStudioDecisionFlowDiagram({
  l2BranchSummary,
  noL2BranchSummary,
  activeUnifiedId,
  legacyComboSourceId,
  legacyTunedSourceId,
  hysteresisBars,
  cooldownBars,
  strategyModeLabel,
}: Props) {
  const hasLegacySources = !!legacyComboSourceId || !!legacyTunedSourceId;

  return (
    <div className="adaptive-section">
      <h3>Decision Flow Diagram</h3>
      <div className="adaptive-flow-diagram">
        <div className="adaptive-flow-node">
          <strong>1) Regime detection</strong>
          <div>Macro + micro regime are refreshed from current bars only.</div>
        </div>
        <div className="adaptive-flow-arrow">↓</div>
        <div className="adaptive-flow-branch-row">
          <div className="adaptive-flow-node">
            <strong>2A) L2 branch</strong>
            <div>{l2BranchSummary}</div>
          </div>
          <div className="adaptive-flow-node">
            <strong>2B) No-L2 branch</strong>
            <div>{noL2BranchSummary}</div>
          </div>
        </div>
        <div className="adaptive-flow-arrow">↓</div>
        <div className="adaptive-flow-node">
          <strong>3) Preference merge</strong>
          <div>Micro preference + macro regime preference + ticker/default candidates.</div>
          <div>
            Unified profile: {activeUnifiedId || "none"}.
            {hasLegacySources && (
              <>
                {" "}
                Legacy sources: {legacyComboSourceId || "combo:none"} / {legacyTunedSourceId || "tuned:none"}.
              </>
            )}
          </div>
        </div>
        <div className="adaptive-flow-arrow">↓</div>
        <div className="adaptive-flow-node">
          <strong>3.5) Switch guard</strong>
          <div>
            Hysteresis: {hysteresisBars} bars. Cooldown: {cooldownBars} bars.
          </div>
        </div>
        <div className="adaptive-flow-arrow">↓</div>
        <div className="adaptive-flow-node highlight">
          <strong>4) Final selection</strong>
          <div>{strategyModeLabel}</div>
        </div>
      </div>
    </div>
  );
}
