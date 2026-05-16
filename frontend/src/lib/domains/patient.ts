export interface PatientMeta {
  patient_id: string;
  age: number | null;
  sex: string | null;
  sex_raw?: string | null;
  weight_kg: number | null;
  doctor_code: string | null;
  comorbidity_conditions: string[];
}

export interface PatientSearchResult {
  patient_id: string;
  age: number | null;
  sex: string | null;
  sex_raw?: string | null;
  weight_kg?: number | null;
  doctor_code?: string | null;
  comorbidity_conditions?: string[];
}

export interface PatientSearchResponse {
  results: PatientSearchResult[];
  total_matched: number;
}

export interface Comorbidity {
  label: string;
  detail: string | null;
}

export interface RegimeTimelinePoint {
  date: string;
  ma: number | null;
  state: string | null;
}

export interface VarFanData {
  history_dates: string[];
  history_scores: number[];
  future_dates: string[];
  p05: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
  risk_tier: string;
  var_pct: number;
}

export interface NlpBar {
  date: string;
  nlp_composite: number;
}

export interface NliScore {
  date: string;
  source: string;
  text: string;
  nli_score: number;
}

export interface LabSeries {
  dates: string[];
  values: number[];
  ref_min: number | null;
  ref_max: number | null;
}

export interface ClinicalNote {
  date: string;
  entries: { source: string; text: string }[];
}

export interface PatientSummary {
  patient_id: string;
  rating: string;
  composite_score: number;
  regime_state: string;
  downside_var_pct: number | null;
  eci_score: number | null;
  eci_rating: string | null;
  eci_rating_label: string | null;
  eci_visit_intensity: number | null;
  eci_med_burden: number | null;
  eci_diagnostic_intensity: number | null;
  eci_trajectory_cost: number | null;
  age: number | null;
  sex: string | null;
  n_comorbidities: number;
  total_visits: number | null;
  n_lab_draws: number;
  n_prescriptions: number;
  data_completeness: number | null;
}

export interface PatientData {
  summary: PatientSummary;
  comorbidities: Comorbidity[];
  regime_timeline: RegimeTimelinePoint[];
  prescription_dates: string[];
  var_fan: VarFanData | null;
  nlp_bars: NlpBar[];
  nli_scores: NliScore[];
  lab_series: Record<string, LabSeries>;
  clinical_notes: ClinicalNote[];
}

export interface PatientFilters {
  gender: string;
  doctor: string;
  comorbidityConditions: string[];
  ageMin: string;
  ageMax: string;
  weightMin: string;
  weightMax: string;
}
