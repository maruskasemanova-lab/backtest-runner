import type { ExecutionModuleField, ExecutionModulesSnapshot } from "../../executionModulesTypes";
import {
  EXECUTION_MODULE_PARAM_FIELDS,
  EXECUTION_MODULE_PROFILE_KEYS,
} from "../../constants/adaptive-studio";
import { toBoolean } from "./adaptiveStudioTransformersCore";

export const normalizeExecutionModulesSnapshot = (
  value: unknown,
): ExecutionModulesSnapshot => {
  const source = value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
  const normalized: ExecutionModulesSnapshot = {};
  EXECUTION_MODULE_PROFILE_KEYS.forEach((key) => {
    normalized[key] = toBoolean(source[key], false);
  });
  return normalized;
};

export const normalizeExecutionParamValue = (
  value: unknown,
  field: ExecutionModuleField,
): unknown => {
  if (field?.type === "boolean") {
    return toBoolean(value, !!field?.fallback);
  }
  if (field?.type === "select") {
    if (field?.key === "stop_loss_mode") {
      const raw = String(value ?? field?.fallback ?? "strategy")
        .trim()
        .toLowerCase();
      if (raw === "fixed" || raw === "capped") return raw;
      return "strategy";
    }
    const options = Array.isArray(field?.options) ? field.options : [];
    const allowed = options
      .map((item) => String(item?.value || "").trim())
      .filter(Boolean);
    const fallback = String(field?.fallback ?? allowed[0] ?? "").trim();
    const candidate = String(value ?? fallback).trim();
    return allowed.includes(candidate) ? candidate : fallback;
  }
  const parsed = Number(value);
  const fallback = Number(field?.fallback || 0);
  const min = Number(field?.min ?? Number.NEGATIVE_INFINITY);
  const max = Number(field?.max ?? Number.POSITIVE_INFINITY);
  const safe = Number.isFinite(parsed) ? parsed : fallback;
  const clamped = Math.max(min, Math.min(max, safe));
  if (field?.integer) {
    return Math.trunc(clamped);
  }
  return clamped;
};

export const normalizeExecutionParamsSnapshot = (
  value: unknown,
): ExecutionModulesSnapshot => {
  const source = value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
  const normalized: ExecutionModulesSnapshot = {};
  EXECUTION_MODULE_PARAM_FIELDS.forEach((field) => {
    normalized[field.key] = normalizeExecutionParamValue(source[field.key], field);
  });
  return normalized;
};

export const readExecutionConfigSnapshot = (): ExecutionModulesSnapshot => {
  if (typeof window === "undefined") return {};
  const raw = (window as typeof window & { __executionConfig?: unknown }).__executionConfig;
  return raw && typeof raw === "object" && !Array.isArray(raw)
    ? (raw as ExecutionModulesSnapshot)
    : {};
};

export const readExecutionModuleSnapshot = (): ExecutionModulesSnapshot => {
  return normalizeExecutionModulesSnapshot(readExecutionConfigSnapshot());
};

export const readExecutionParamsSnapshot = (): ExecutionModulesSnapshot => {
  return normalizeExecutionParamsSnapshot(readExecutionConfigSnapshot());
};

export const applyExecutionModuleSnapshot = (value: unknown): void => {
  if (typeof window === "undefined") return;
  const normalized = normalizeExecutionModulesSnapshot(value);
  Object.entries(normalized).forEach(([configKey, enabled]) => {
    window.dispatchEvent(
      new CustomEvent("execution-module-toggle", {
        detail: { configKey, value: !!enabled },
      }),
    );
  });
};

export const applyExecutionParamsSnapshot = (value: unknown): void => {
  if (typeof window === "undefined") return;
  const normalized = normalizeExecutionParamsSnapshot(value);
  Object.entries(normalized).forEach(([configKey, nextValue]) => {
    window.dispatchEvent(
      new CustomEvent("execution-module-toggle", {
        detail: { configKey, value: nextValue },
      }),
    );
  });
};
