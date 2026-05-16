import type {
  PatientAlertsCategory,
  PatientAlertsRequestParams,
  PatientAlertsStatus,
} from "@/lib/domains/sut";

export const ALERT_PAGE_SIZE = 100;

const ALERT_STATUS_OPTIONS: Record<PatientAlertsCategory, readonly PatientAlertsStatus[]> = {
  exemptions: ["all", "exempt", "not_exempt"],
  surcharge: ["all", "flagged", "clear"],
  copay_rates: ["all", "flagged", "clear"],
} as const;

const ALERT_STATUS_LABELS: Record<PatientAlertsStatus, string> = {
  all: "All",
  exempt: "Exempt",
  not_exempt: "Not Exempt",
  flagged: "Flagged",
  clear: "Clear",
};

export function getAlertStatusOptions(category: PatientAlertsCategory): readonly PatientAlertsStatus[] {
  return ALERT_STATUS_OPTIONS[category];
}

export function getAlertStatusLabel(status: PatientAlertsStatus): string {
  return ALERT_STATUS_LABELS[status];
}

export function buildPatientAlertsQuery(
  params: {
    category: PatientAlertsCategory;
    status: PatientAlertsStatus;
    search: string;
    page: number;
    limit?: number;
  },
): PatientAlertsRequestParams {
  const limit = params.limit ?? ALERT_PAGE_SIZE;
  return {
    category: params.category,
    status: params.status,
    search: params.search.trim(),
    limit,
    offset: Math.max(params.page - 1, 0) * limit,
  };
}

export function parseAlertPageInput(value: string): number | null {
  const digitsOnly = value.replace(/[^\d]/g, "");
  if (!digitsOnly) {
    return null;
  }

  const parsed = Number.parseInt(digitsOnly, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

export function clampAlertPage(page: number, totalPages: number): number {
  const safeTotalPages = Math.max(1, Math.trunc(totalPages));
  const safePage = Number.isFinite(page) ? Math.trunc(page) : 1;
  return Math.min(Math.max(safePage, 1), safeTotalPages);
}
