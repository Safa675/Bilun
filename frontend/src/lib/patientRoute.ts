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

/**
 * Find the exact unified finding row for a `?finding=` deep link.
 *
 * Uses dataset equality instead of embedding the raw id in a CSS selector
 * so canonical ids with special characters (`:`, `/`, spaces, `&`) resolve
 * without selector-escaping bugs.
 */
export function findFindingRowElement(
  root: ParentNode,
  findingId: string | null | undefined,
): Element | null {
  if (!findingId) return null;
  const candidates = root.querySelectorAll("[data-finding-id]");
  for (const element of candidates) {
    if ((element as HTMLElement).dataset?.findingId === findingId) {
      return element;
    }
  }
  return null;
}

/**
 * Resolve the patient-page scroll target with exact-finding priority.
 *
 * 1. When `findingId` is present, the exact `data-finding-id` row wins.
 * 2. Otherwise (or when the exact row is not yet in the DOM), fall back to
 *    the `section` anchor.
 * 3. When neither resolves, return null (no-op).
 */
export function resolvePatientScrollTarget(
  root: ParentNode & { getElementById?: (id: string) => Element | null },
  findingId: string | null | undefined,
  sectionId: string | null | undefined,
): Element | null {
  if (findingId) {
    const exact = findFindingRowElement(root, findingId);
    if (exact) return exact;
  }
  if (sectionId) {
    const section = typeof root.getElementById === "function"
      ? root.getElementById(sectionId)
      : Array.from(root.querySelectorAll("[id]")).find((element) => element.id === sectionId);
    if (section) return section;
  }
  return null;
}
