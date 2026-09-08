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
