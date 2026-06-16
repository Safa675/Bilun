"use client";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/useTranslations";
import { useSetUserRole, useUserRole } from "@/components/shell/RoleProvider";
import type { UserRole } from "@/lib/userRole";

const ROLES: UserRole[] = ["billing_officer", "dev"];

export default function RoleSwitcher() {
  const role = useUserRole();
  const setRole = useSetUserRole();
  const t = useT();

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="role-switcher" className="sr-only">
        {t("shell.role.groupLabel")}
      </label>
      <select
        id="role-switcher"
        value={role}
        onChange={(e) => setRole(e.target.value as UserRole)}
        aria-label={t("shell.role.groupLabel")}
        className={cn(
          "h-7 min-w-[8rem] rounded-[var(--r-md)] border border-[var(--border-subtle)]",
          "bg-[var(--surface-base)] px-2 text-xs font-medium text-[var(--text-primary)]",
          "focus:outline-none focus:ring-1 focus:ring-[var(--gold)]",
        )}
      >
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {t(`shell.role.${r}`)}
          </option>
        ))}
      </select>
    </div>
  );
}
