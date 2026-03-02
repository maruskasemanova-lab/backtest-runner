import { z } from "zod";

export const numberLikeSchema = z.union([z.number(), z.string(), z.null()]);
export const nullableStringSchema = z.union([z.string(), z.null()]);
export const stringArraySchema = z.array(z.string());
export const objectRecordSchema = z.record(z.string(), z.unknown());

export const profileSourceSchema = z.object({
  active_profile_id: nullableStringSchema.optional(),
  candidate_applied: z.boolean().optional(),
  profile_id: nullableStringSchema.optional(),
  profile_name: nullableStringSchema.optional(),
}).passthrough();

export const aosAppliedSchema = z.object({
  adaptive_profile: profileSourceSchema.optional(),
  strategy_combo: profileSourceSchema.optional(),
  unified_profile: profileSourceSchema.optional(),
}).passthrough();

export const tradeSchema = z.object({
  bars_held: numberLikeSchema.optional(),
  entry_reason: nullableStringSchema.optional(),
  entry_time: nullableStringSchema.optional(),
  exit_reason: nullableStringSchema.optional(),
  exit_time: nullableStringSchema.optional(),
  pnl_dollars: numberLikeSchema.optional(),
  report_dir: nullableStringSchema.optional(),
  run_id: nullableStringSchema.optional(),
  side: nullableStringSchema.optional(),
  strategy: nullableStringSchema.optional(),
  trade_id: z.union([z.string(), z.number(), z.null()]).optional(),
}).passthrough();

export const runSchema = z.object({
  account_size_usd: numberLikeSchema.optional(),
  adaptive_profile_id: nullableStringSchema.optional(),
  adaptive_profile_name: nullableStringSchema.optional(),
  aos_applied: aosAppliedSchema.optional(),
  date_label: z.string().optional(),
  execution_config: objectRecordSchema.optional(),
  pnl_dollars: numberLikeSchema.optional(),
  processed_bars: numberLikeSchema.optional(),
  profile_match_mode: nullableStringSchema.optional(),
  regime_evaluations: numberLikeSchema.optional(),
  report_dir: z.string().optional(),
  report_saved_at: z.string().optional(),
  run_key: z.string().optional(),
  run_processed_bars: numberLikeSchema.optional(),
  run_regime_evaluations: numberLikeSchema.optional(),
  run_request_config: objectRecordSchema.optional(),
  run_signals: numberLikeSchema.optional(),
  run_total_bars: numberLikeSchema.optional(),
  run_total_pnl_dollars: numberLikeSchema.optional(),
  run_total_trades: numberLikeSchema.optional(),
  run_id: z.string().optional(),
  signals: numberLikeSchema.optional(),
  strategy_combo_profile_id: nullableStringSchema.optional(),
  strategy_combo_profile_name: nullableStringSchema.optional(),
  strategy_names: stringArraySchema.optional(),
  total_bars: numberLikeSchema.optional(),
  total_trades: numberLikeSchema.optional(),
  unified_profile_id: nullableStringSchema.optional(),
  unified_profile_name: nullableStringSchema.optional(),
}).passthrough();

export const dayResultSchema = z.object({
  account_size_usd: numberLikeSchema.optional(),
  adaptive_profile_id: nullableStringSchema.optional(),
  adaptive_profile_ids: stringArraySchema.optional(),
  adaptive_profile_name: nullableStringSchema.optional(),
  adaptive_profile_names: stringArraySchema.optional(),
  aos_applied: aosAppliedSchema.optional(),
  date: z.string(),
  error: z.unknown().optional(),
  execution_config: objectRecordSchema.optional(),
  pnl_dollars: numberLikeSchema.optional(),
  profile_match_modes: stringArraySchema.optional(),
  processed_bars: numberLikeSchema.optional(),
  regime_evaluations: numberLikeSchema.optional(),
  report_count: numberLikeSchema.optional(),
  run_request_config: objectRecordSchema.optional(),
  runs: z.array(runSchema).optional(),
  signals: numberLikeSchema.optional(),
  strategy_combo_profile_id: nullableStringSchema.optional(),
  strategy_combo_profile_ids: stringArraySchema.optional(),
  strategy_combo_profile_name: nullableStringSchema.optional(),
  strategy_combo_profile_names: stringArraySchema.optional(),
  strategy_names: stringArraySchema.optional(),
  success: z.boolean().optional(),
  total_bars: numberLikeSchema.optional(),
  total_trades: numberLikeSchema.optional(),
  trade_details: z.array(tradeSchema).optional(),
  unified_profile_id: nullableStringSchema.optional(),
  unified_profile_ids: stringArraySchema.optional(),
  unified_profile_name: nullableStringSchema.optional(),
  unified_profile_names: stringArraySchema.optional(),
}).passthrough();

export const filterProfileOptionSchema = z.object({
  active: z.boolean().optional(),
  profile_id: z.string(),
  profile_name: z.string().optional(),
  source: z.string().optional(),
}).passthrough();

export const runIdOptionSchema = z.object({
  latest_saved_at: z.string().optional(),
  run_id: z.string(),
}).passthrough();

export const splitSchema = z.object({
  end: nullableStringSchema.optional(),
  start: nullableStringSchema.optional(),
}).passthrough();

export const filterOptionsSchema = z.object({
  adaptive_profiles: z.array(filterProfileOptionSchema).optional(),
  run_ids: z.array(runIdOptionSchema).optional(),
  unified_profiles: z.array(filterProfileOptionSchema).optional(),
}).passthrough();

export const diagnosticCalendarReportSchema = z.object({
  day_results: z.array(dayResultSchema).optional().default([]),
  filter_options: filterOptionsSchema.optional(),
  source_mode: z.string().optional(),
  source_path_hint: z.string().optional(),
  split: splitSchema.optional(),
}).passthrough();

export type DiagnosticCalendarReport = z.infer<typeof diagnosticCalendarReportSchema>;
export type DiagnosticCalendarTrade = z.infer<typeof tradeSchema>;
export type DiagnosticCalendarRun = z.infer<typeof runSchema>;
export type DiagnosticCalendarDayResult = z.infer<typeof dayResultSchema>;
export type DiagnosticCalendarFilterProfileOption = z.infer<typeof filterProfileOptionSchema>;
export type DiagnosticCalendarRunIdOption = z.infer<typeof runIdOptionSchema>;

export const parseDiagnosticCalendarReport = (payload: unknown): DiagnosticCalendarReport => {
  const parsed = diagnosticCalendarReportSchema.safeParse(payload);
  if (parsed.success) return parsed.data;

  const [issue] = parsed.error.issues;
  const path = issue?.path?.length ? issue.path.join(".") : "root";
  const message = issue?.message || "Unknown validation error";
  throw new Error(`Invalid diagnostic calendar report payload at ${path}: ${message}`);
};
