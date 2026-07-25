/**
 * Fixture money formatting for component tests.
 *
 * Matches the common `vi.mock` of `@/components/tabs/sut/shared` fmtTRY2.
 * Real locale/formatter behavior is covered once in `shared.test.ts` —
 * component tests should derive expected strings from fixture numbers via
 * these helpers, not hardcode `"800.00 TRY"` literals.
 */

export function fmtTRY2Fixture(value: number): string {
  return `${value.toFixed(2)} TRY`;
}

export function fmtTRYFixture(value: number): string {
  return `${value} TRY`;
}
