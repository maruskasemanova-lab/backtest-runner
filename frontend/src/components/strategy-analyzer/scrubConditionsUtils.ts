import { extractRunBarAnalysis } from "./extractRunBarAnalysis";
import { toUnixSeconds } from "../../utils";
import type {
  StrategyAnalyzerConditionsRangeScrubMeta,
  StrategyAnalyzerDecisionMarker,
  StrategyAnalyzerRunBarAnalysisSnapshot,
} from "./types";

const SCRUB_DECISION_MARKER_TYPE_PRIORITIES: Record<string, number> = {
  execution_status: 90,
  entry_executed: 40,
  signal_generated: 30,
  exit_executed: 20,
  stop_loss_hit: 20,
  take_profit_hit: 20,
  trailing_stop_updated: 10,
};

function preferSnapshotField<K extends keyof StrategyAnalyzerRunBarAnalysisSnapshot>(
  key: K,
  checkpointSnapshot: StrategyAnalyzerRunBarAnalysisSnapshot,
  direct: StrategyAnalyzerRunBarAnalysisSnapshot,
) {
  return checkpointSnapshot[key] ?? direct[key] ?? null;
}

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
      intrabar_1s: preferSnapshotField("intrabar_1s", checkpointSnapshot, direct),
      intrabar_eval_trace: preferSnapshotField("intrabar_eval_trace", checkpointSnapshot, direct),
      intraday_levels: preferSnapshotField("intraday_levels", checkpointSnapshot, direct),
      intrabar_confirmation: preferSnapshotField("intrabar_confirmation", checkpointSnapshot, direct),
      micro_confirmation: preferSnapshotField("micro_confirmation", checkpointSnapshot, direct),
      level_context: preferSnapshotField("level_context", checkpointSnapshot, direct),
      context_risk: preferSnapshotField("context_risk", checkpointSnapshot, direct),
      entry_quality_diagnostics: preferSnapshotField(
        "entry_quality_diagnostics",
        checkpointSnapshot,
        direct,
      ),
      tcbbo_confirmation: preferSnapshotField("tcbbo_confirmation", checkpointSnapshot, direct),
      timestamp: preferSnapshotField("timestamp", checkpointSnapshot, direct),
      bar_action: preferSnapshotField("bar_action", checkpointSnapshot, direct),
      bar_reason: preferSnapshotField("bar_reason", checkpointSnapshot, direct),
      bar_index: checkpointSnapshot.bar_index ?? direct.bar_index ?? null,
      checkpoint_offset_sec: checkpointSnapshot.checkpoint_offset_sec ?? direct.checkpoint_offset_sec ?? null,
      provisional: checkpointSnapshot.provisional ?? direct.provisional ?? null,
      warmup_only: Boolean(checkpointSnapshot.warmup_only ?? direct.warmup_only),
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

function scoreScrubMarkerEvidence(marker: StrategyAnalyzerDecisionMarker): number {
  const details = marker?.details;
  if (!details || typeof details !== "object") return 0;

  let score = 0;
  if (details.context_risk && typeof details.context_risk === "object") score += 40;
  if (details.signal_rejected && typeof details.signal_rejected === "object") score += 20;
  if (details.layer_scores && typeof details.layer_scores === "object") score += 10;
  if (details.candidate_diagnostics && typeof details.candidate_diagnostics === "object") score += 8;
  if (details.level_context && typeof details.level_context === "object") score += 6;
  return score;
}

export function resolveScrubbedDecisionMarker(
  rangeScrubMeta: StrategyAnalyzerConditionsRangeScrubMeta,
  markers: StrategyAnalyzerDecisionMarker[],
): StrategyAnalyzerDecisionMarker | null {
  const sourceMarkers = Array.isArray(markers) ? markers : [];
  if (!rangeScrubMeta || !sourceMarkers.length) return null;

  const targetTime = Number(rangeScrubMeta?.targetTime);
  const targetMinute = Number.isFinite(targetTime) ? Math.floor(targetTime / 60) : null;
  const targetBarIndex = Number(
    rangeScrubMeta?.targetBar?.bar_index ?? rangeScrubMeta?.targetCheckpoint?.bar_index,
  );

  let bestMarker: StrategyAnalyzerDecisionMarker | null = null;
  let bestScore = Number.NEGATIVE_INFINITY;
  let bestTime = Number.NEGATIVE_INFINITY;
  let bestBarIndex = Number.NEGATIVE_INFINITY;

  for (const marker of sourceMarkers) {
    if (!marker || typeof marker !== "object") continue;

    const markerType = String(marker.marker_type || "").trim();
    if (!markerType) continue;

    const typePriority = SCRUB_DECISION_MARKER_TYPE_PRIORITIES[markerType];
    if (!Number.isFinite(typePriority)) continue;

    const markerBarIndex = Number(marker.bar_index);
    const markerTime = toUnixSeconds(marker.time ?? marker.timestamp);
    const sameBarIndex =
      Number.isFinite(targetBarIndex) &&
      Number.isFinite(markerBarIndex) &&
      markerBarIndex === targetBarIndex;
    const sameMinute =
      Number.isFinite(targetTime) &&
      Number.isFinite(markerTime) &&
      Math.floor(markerTime / 60) === targetMinute;

    if (!sameBarIndex && !sameMinute) continue;

    let score = typePriority + scoreScrubMarkerEvidence(marker);
    if (sameBarIndex) score += 200;

    if (Number.isFinite(targetTime) && Number.isFinite(markerTime)) {
      const deltaSeconds = Math.abs(markerTime - targetTime);
      if (deltaSeconds <= 1) {
        score += 120;
      } else if (sameMinute) {
        score += Math.max(0, 60 - deltaSeconds);
      }
    } else if (sameMinute) {
      score += 40;
    }

    const tieBreakerTime = Number.isFinite(markerTime) ? markerTime : Number.NEGATIVE_INFINITY;
    const tieBreakerBarIndex = Number.isFinite(markerBarIndex)
      ? markerBarIndex
      : Number.NEGATIVE_INFINITY;

    if (
      score > bestScore ||
      (score === bestScore && tieBreakerTime > bestTime) ||
      (score === bestScore &&
        tieBreakerTime === bestTime &&
        tieBreakerBarIndex > bestBarIndex)
    ) {
      bestMarker = marker;
      bestScore = score;
      bestTime = tieBreakerTime;
      bestBarIndex = tieBreakerBarIndex;
    }
  }

  return bestMarker;
}

export function hasDecisionPayload(
  snapshot: StrategyAnalyzerRunBarAnalysisSnapshot | null
): boolean {
  if (!snapshot || typeof snapshot !== "object") return false;
  return Boolean(
    (snapshot.layer_scores && typeof snapshot.layer_scores === "object") ||
      (snapshot.signal_rejected && typeof snapshot.signal_rejected === "object") ||
      (snapshot.candidate_diagnostics && typeof snapshot.candidate_diagnostics === "object") ||
      (snapshot.level_context && typeof snapshot.level_context === "object") ||
      (snapshot.context_risk && typeof snapshot.context_risk === "object") ||
      (snapshot.entry_quality_diagnostics &&
        typeof snapshot.entry_quality_diagnostics === "object") ||
      (snapshot.intrabar_confirmation && typeof snapshot.intrabar_confirmation === "object") ||
      (snapshot.micro_confirmation && typeof snapshot.micro_confirmation === "object") ||
      (snapshot.tcbbo_confirmation && typeof snapshot.tcbbo_confirmation === "object")
  );
}
