export const SUT_WORKSPACE_STORAGE_KEY = "ilay-sut-workspace-entered";

export function shouldEnterSutWorkspace(
  tabQuery: string | null | undefined,
  persistedValue: string | null | undefined,
): boolean {
  return Boolean(tabQuery) || persistedValue === "1";
}
