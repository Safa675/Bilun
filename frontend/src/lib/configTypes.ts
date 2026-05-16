/**
 * TypeScript types for the /api/frontend-config response.
 *
 * Every domain constant the frontend needs is defined here.
 * No thresholds, weights, or classification logic should be
 * hardcoded in components — use useConfig() instead.
 */

import type { SUTDataSourceMetadata } from "./domains/sut";

/* ── Risk classification ─────────────────────────────────────────────── */

export interface RiskTier {
  /** Minimum IHP score for this tier (inclusive) */
  min: number;
  /** Backend key: "dusuk" | "orta" | "yuksek" | "kritik" */
  key: string;
  /** Display label: "Low Risk" | "Moderate" | "High" | "Critical" */
  label: string;
  /** Hex color for this tier */
  color: string;
}

/* ── Composite score → letter rating ─────────────────────────────────── */

export interface RatingTier {
  /** Minimum composite score for this rating (inclusive) */
  min: number;
  /** Letter rating: "AAA" | "AA" | "A" | "BBB" | "BB" | "B/CCC" */
  rating: string;
  /** Display label: "Excellent" | "Very Good" | etc. */
  label: string;
  /** Hex color */
  color: string;
}

/* ── Subscore configuration ──────────────────────────────────────────── */

export interface SubscoreConfig {
  /** Normalized weight (0–1, sums to ~1.0 across all subscores) */
  weight: number;
  /** Display label: "Demographics", "Disease Burden", etc. */
  label: string;
  /** Feature column names feeding this subscore */
  features: string[];
}

/* ── Direction display metadata ──────────────────────────────────────── */

export interface DirectionStyle {
  /** Unicode arrow character */
  arrow: string;
  /** Hex color */
  color: string;
  /** Display label: "Rapidly Declining", "Stable", etc. */
  label: string;
}

/* ── Performance metadata ────────────────────────────────────────────── */

export interface ActiveModelPerformance {
  /** Display label for the current model */
  label: string;
  /** Model engine, e.g. "ebm" */
  engine: string;
  /** Training target, e.g. "target_3m" */
  target: string | null;
  /** Artifact creation timestamp */
  created_at: string | null;
  /** Total model feature count */
  n_features: number | null;
  /** Grouped subscore/domain count */
  n_subscores: number | null;
  /** Ordered grouped subscore names */
  subscore_names: string[];
  /** Cross-validated training AUC */
  training_auc: number | null;
  /** Cross-validated training PR-AUC */
  training_pr_auc: number | null;
  /** Cross-validated training Brier score */
  training_brier: number | null;
  /** Number of CV folds */
  n_folds: number | null;
  /** Total training samples */
  n_samples: number | null;
  /** Positive training samples */
  n_positive: number | null;
  /** Positive class rate */
  positive_rate: number | null;
}

export interface PerformanceConfig {
  active_model: ActiveModelPerformance | null;
}

/* ── Regulatory gazette counts ───────────────────────────────────────── */

export interface RegulatoryConfig {
  /** EK-1A chronic disease copayment exemption ranges */
  ek1a_exemption_count: number;
  /** EK-2G no-surcharge procedures */
  ek2g_procedure_count: number;
  /** EK-2C-1 copayment rate-capped procedures */
  ek2c1_procedure_count: number;
}

/* ── Cost tiers ──────────────────────────────────────────────────────── */

export interface CostTier {
  /** Minimum cost (TRY) for this tier */
  min: number;
  /** Display label: "Very High Cost", "High Cost", etc. */
  label: string;
}

/* ── Regime state display ────────────────────────────────────────────── */

export interface RegimeStateStyle {
  /** Hex color */
  color: string;
  /** Emoji indicator */
  emoji: string;
}

/* ── Full config response ────────────────────────────────────────────── */

export interface FrontendConfig {
  risk_tiers: RiskTier[];
  rating_tiers: RatingTier[];
  subscores: Record<string, SubscoreConfig>;
  directions: Record<string, DirectionStyle>;
  regime_states: Record<string, RegimeStateStyle>;
  performance: PerformanceConfig;
  regulatory: RegulatoryConfig;
  cost_tiers: CostTier[];
  sut_data_source?: SUTDataSourceMetadata | null;
  sutDataSource?: SUTDataSourceMetadata | null;
}

/* ── Helpers for looking up tiers ────────────────────────────────────── */

/** Find the risk tier for a given IHP score. Tiers must be sorted descending by min. */
export function findRiskTier(tiers: RiskTier[], score: number): RiskTier {
  for (const tier of tiers) {
    if (score >= tier.min) return tier;
  }
  return tiers[tiers.length - 1];
}

/** Find the rating tier for a given composite score. Tiers must be sorted descending by min. */
export function findRatingTier(tiers: RatingTier[], score: number): RatingTier {
  for (const tier of tiers) {
    if (score >= tier.min) return tier;
  }
  return tiers[tiers.length - 1];
}

/** Build a Record<riskKey, color> from risk tiers for quick lookups. */
export function riskColorMap(tiers: RiskTier[]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const t of tiers) map[t.key] = t.color;
  return map;
}

/** Build a Record<rating, color> from rating tiers. */
export function ratingColorMap(tiers: RatingTier[]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const t of tiers) map[t.rating] = t.color;
  return map;
}

/** Build a Record<rating, label> from rating tiers. */
export function ratingLabelMap(tiers: RatingTier[]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const t of tiers) map[t.rating] = t.label;
  return map;
}

/** Get color for a score based on risk tiers. Tiers must be sorted descending by min. */
export function getScoreColor(tiers: RiskTier[], score: number): string {
  for (const tier of tiers) {
    if (score >= tier.min) return tier.color;
  }
  return tiers[tiers.length - 1]?.color ?? "#B91C1C";
}

/** Get risk tier key for a score. Returns the key (e.g., "dusuk", "orta", "yuksek", "kritik") */
export function getScoreTier(tiers: RiskTier[], score: number): string {
  for (const tier of tiers) {
    if (score >= tier.min) return tier.key;
  }
  return tiers[tiers.length - 1]?.key ?? "kritik";
}
