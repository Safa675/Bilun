"use client";

import { UserCog } from "lucide-react";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/useTranslations";
import { useSetUserRole, useUserRole } from "@/components/shell/RoleProvider";
import type { UserRole } from "@/lib/userRole";

const ROLES: UserRole[] = ["billing_officer", "dev"];

export default function RoleSwitcher({ compact = false }: { compact?: boolean }) {
  const role = useUserRole();
  const setRole = useSetUserRole();
  const t = useT();

  if (compact) {
    const nextRole = ROLES[(ROLES.indexOf(role) + 1) % ROLES.length] ?? "dev";
    return (
      <button
        type="button"
        onClick={() => setRole(nextRole)}
        className={cn(
          "inline-flex h-8 w-8 items-center justify-center rounded-[var(--r-md)]",
          "border border-[var(--border-subtle)] text-[var(--text-muted)]",
          "hover:bg-[var(--surface-tint)] hover:text-[var(--text-primary)]",
          "transition-colors",
        )}
        aria-label={`${t("shell.role.groupLabel")}: ${t(`shell.role.${role}`)}`}
        title={`${t("shell.role.groupLabel")}: ${t(`shell.role.${role}`)}`}
      >
        <UserCog className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    );
  }

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
