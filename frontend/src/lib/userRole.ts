export type UserRole = "billing_officer" | "dev";

/** Legacy preferences are removed on entry; they never determine permission. */
export const ROLE_STORAGE_KEY = "bilun_user_role";
export const ROLE_COOKIE_KEY = "bilun:role";
