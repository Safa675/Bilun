export interface PatientWorkspaceQuery {
  claimId: string | null;
  section: string | null;
  findingId: string | null;
}

type SearchParamsLike = Pick<URLSearchParams, "get">;

export function parsePatientWorkspaceQuery(
  searchParams: SearchParamsLike,
): PatientWorkspaceQuery {
  return {
    claimId: searchParams.get("claim"),
    section: searchParams.get("section"),
    findingId: searchParams.get("finding"),
  };
}
