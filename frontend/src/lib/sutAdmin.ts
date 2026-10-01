export function isSutAdminEnabled(value: string | null | undefined, developer = false): boolean {
  return developer && value === "1";
}
