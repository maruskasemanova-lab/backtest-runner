import { extractRunBarAnalysis } from "./extractRunBarAnalysis";
import type {
  StrategyAnalyzerConditionsRangeScrubMeta,
  StrategyAnalyzerRunBarAnalysisSnapshot,
} from "./types";

export function deriveScrubbedLiveAnalysis(
  rangeScrubMeta: StrategyAnalyzerConditionsRangeScrubMeta
): StrategyAnalyzerRunBarAnalysisSnapshot | null {
  const checkpointSnapshot = extractRunBarAnalysis(rangeScrubMeta?.targetCheckpoint);
  const targetBar = rangeScrubMeta?.targetBar;
  const direct = extractRunBarAnalysis(targetBar);
  if (checkpointSnapshot && direct) {
    const hasCheckpointScores = Boolean(checkpointSnapshot.layer_scores);
    const hasParentScores = Boolean(direct.layer_scores);
    return {
      ...direct,
      ...checkpointSnapshot,
      layer_scores: hasCheckpointScores ? checkpointSnapshot.layer_scores : direct.layer_scores,
      signal_rejected: hasCheckpointScores
        ? (checkpointSnapshot.signal_rejected ?? direct.signal_rejected)
        : direct.signal_rejected,
      candidate_diagnostics: hasCheckpointScores
        ? (checkpointSnapshot.candidate_diagnostics ?? direct.candidate_diagnostics)
        : direct.candidate_diagnostics,
      intrabar_only_checkpoint:
        hasCheckpointScores || hasParentScores ? false : checkpointSnapshot.intrabar_only_checkpoint,
      checkpoint_mode: hasCheckpointScores
        ? true
        : hasParentScores
          ? false
          : checkpointSnapshot.checkpoint_mode,
    } as StrategyAnalyzerRunBarAnalysisSnapshot;
  }
  if (checkpointSnapshot) return checkpointSnapshot;
  if (direct) return direct;

  const progressed = Array.isArray(rangeScrubMeta?.progressedTradeBars)
    ? rangeScrubMeta.progressedTradeBars
    : [];
  const targetTime = Number(rangeScrubMeta?.targetTime);
  if (!progressed.length || !Number.isFinite(targetTime)) return null;

  for (let i = progressed.length - 1; i >= 0; i -= 1) {
    const bar = progressed[i];
    const t = Number(bar?.time);
    if (!Number.isFinite(t) || t > targetTime + 1) continue;
    const snapshot = extractRunBarAnalysis(bar);
    if (snapshot) return snapshot;
  }

  for (let i = 0; i < progressed.length; i += 1) {
    const bar = progressed[i];
    const t = Number(bar?.time);
    if (!Number.isFinite(t) || t < targetTime - 1) continue;
    const snapshot = extractRunBarAnalysis(bar);
    if (snapshot) return snapshot;
  }

  return null;
}

export function hasDecisionPayload(
  snapshot: StrategyAnalyzerRunBarAnalysisSnapshot | null
): boolean {
  if (!snapshot || typeof snapshot !== "object") return false;
  return Boolean(
    (snapshot.layer_scores && typeof snapshot.layer_scores === "object") ||
      (snapshot.signal_rejected && typeof snapshot.signal_rejected === "object") ||
      (snapshot.candidate_diagnostics && typeof snapshot.candidate_diagnostics === "object")
  );
}
