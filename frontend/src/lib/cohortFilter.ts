import type { ReadonlyURLSearchParams } from "next/navigation";
import type { PatientMeta } from "@/lib/domains/patient";
import type { SutHomeTab } from "@/lib/constants";

export interface CohortFilter {
  /** Selected patient ID (exact match) */
  q: string;
  sex: "" | "E" | "K";
  ageMin: number | null;
  ageMax: number | null;
  doctor: string;
}

export const EMPTY_COHORT_FILTER: CohortFilter = {
  q: "",
  sex: "",
  ageMin: null,
  ageMax: null,
  doctor: "",
};

export const COHORT_FILTER_PARAM_KEYS = [
  "cohortQ",
  "cohortSex",
  "cohortAgeMin",
  "cohortAgeMax",
  "cohortDoctor",
] as const;

function parseAgeParam(value: string | null): number | null {
  if (!value?.trim()) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

/** Parse a single age-range field such as "20 - 30" or "40". */
export function parseAgeRangeInput(value: string): Pick<CohortFilter, "ageMin" | "ageMax"> {
  const trimmed = value.trim();
  if (!trimmed) {
    return { ageMin: null, ageMax: null };
  }

  const rangeMatch = trimmed.match(/^(\d+)\s*[-–—]\s*(\d+)$/);
  if (rangeMatch) {
    return {
      ageMin: parseAgeParam(rangeMatch[1]),
      ageMax: parseAgeParam(rangeMatch[2]),
    };
  }

  const single = parseAgeParam(trimmed);
  if (single !== null) {
    return { ageMin: single, ageMax: single };
  }

  return { ageMin: null, ageMax: null };
}

export function formatAgeRangeDisplay(filter: Pick<CohortFilter, "ageMin" | "ageMax">): string {
  if (filter.ageMin === null && filter.ageMax === null) return "";
  if (filter.ageMin !== null && filter.ageMax !== null) {
    if (filter.ageMin === filter.ageMax) return String(filter.ageMin);
    return `${filter.ageMin} - ${filter.ageMax}`;
  }
  if (filter.ageMin !== null) return `${filter.ageMin} -`;
  return `- ${filter.ageMax}`;
}

export function formatPatientFilterLabel(meta: PatientMeta): string {
  const details: string[] = [];
  if (meta.age !== null) details.push(`${meta.age}y`);
  if (meta.sex) details.push(meta.sex);
  return details.length > 0
    ? `${meta.patient_id} · ${details.join(" · ")}`
    : meta.patient_id;
}

export function parseCohortFilter(
  params: Pick<URLSearchParams, "get"> | ReadonlyURLSearchParams | null | undefined,
): CohortFilter {
  if (!params) return { ...EMPTY_COHORT_FILTER };
  const sex = params.get("cohortSex");
  return {
    q: params.get("cohortQ")?.trim() ?? "",
    sex: sex === "E" || sex === "K" ? sex : "",
    ageMin: parseAgeParam(params.get("cohortAgeMin")),
    ageMax: parseAgeParam(params.get("cohortAgeMax")),
    doctor: params.get("cohortDoctor")?.trim() ?? "",
  };
}

export function cohortFilterIsActive(filter: CohortFilter): boolean {
  return (
    filter.q.length > 0
    || filter.sex !== ""
    || filter.ageMin !== null
    || filter.ageMax !== null
    || filter.doctor.length > 0
  );
}

export function matchesCohortFilter(meta: PatientMeta, filter: CohortFilter): boolean {
  if (!cohortFilterIsActive(filter)) return true;

  if (filter.q && meta.patient_id.toLowerCase() !== filter.q.toLowerCase()) {
    return false;
  }

  if (filter.sex && meta.sex?.toUpperCase() !== filter.sex) {
    return false;
  }

  if (filter.ageMin !== null) {
    if (meta.age === null || meta.age < filter.ageMin) return false;
  }

  if (filter.ageMax !== null) {
    if (meta.age === null || meta.age > filter.ageMax) return false;
  }

  if (filter.doctor) {
    const doctor = meta.doctor_code?.trim().toLowerCase() ?? "";
    if (!doctor.includes(filter.doctor.toLowerCase())) return false;
  }

  return true;
}

export function buildCohortPatientIdSet(
  patientMeta: PatientMeta[],
  filter: CohortFilter,
): Set<string> {
  if (!cohortFilterIsActive(filter)) {
    return new Set(patientMeta.map((meta) => meta.patient_id));
  }
  return new Set(
    patientMeta.filter((meta) => matchesCohortFilter(meta, filter)).map((meta) => meta.patient_id),
  );
}

export function applyCohortFilterToSearchParams(
  params: URLSearchParams,
  filter: CohortFilter,
): void {
  const setOrDelete = (key: string, value: string | null) => {
    if (value && value.length > 0) params.set(key, value);
    else params.delete(key);
  };

  setOrDelete("cohortQ", filter.q || null);
  setOrDelete("cohortSex", filter.sex || null);
  setOrDelete(
    "cohortAgeMin",
    filter.ageMin !== null ? String(filter.ageMin) : null,
  );
  setOrDelete(
    "cohortAgeMax",
    filter.ageMax !== null ? String(filter.ageMax) : null,
  );
  setOrDelete("cohortDoctor", filter.doctor || null);
}

export function copyCohortFilterParams(
  source: Pick<URLSearchParams, "get"> | ReadonlyURLSearchParams | null | undefined,
  target: URLSearchParams,
): void {
  if (!source) return;
  for (const key of COHORT_FILTER_PARAM_KEYS) {
    const value = source.get(key);
    if (value) target.set(key, value);
  }
}

export function buildSutHomeSearchParams(
  tab: SutHomeTab,
  options?: {
    preserveParams?: Pick<URLSearchParams, "get"> | ReadonlyURLSearchParams | null;
    cohort?: CohortFilter;
    admin?: string | null;
  },
): URLSearchParams {
  const params = new URLSearchParams();
  params.set("tab", tab);

  if (options?.preserveParams) {
    copyCohortFilterParams(options.preserveParams, params);
  }

  if (options?.cohort) {
    applyCohortFilterToSearchParams(params, options.cohort);
  }

  const admin = options?.admin ?? options?.preserveParams?.get("admin");
  if (admin) params.set("admin", admin);

  return params;
}

export function buildSutHomeHrefFromParams(params: URLSearchParams): string {
  const query = params.toString();
  return query ? `/?${query}` : "/";
}
