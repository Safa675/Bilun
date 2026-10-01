"use client";

import Link from "next/link";
import { UserCog } from "lucide-react";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/useTranslations";
import { useSessionIdentity } from "@/components/shell/RoleProvider";
import { canUseDeveloper } from "@/lib/auth";

/** The historical component name remains; users can no longer select permission. */
export default function RoleSwitcher({ compact = false }: { compact?: boolean }) {
  const identity = useSessionIdentity();
  const t = useT();
  const developer = canUseDeveloper(identity);
  const label = developer ? t("shell.role.dev") : t("auth.login.developerSignIn");
  const content = <><UserCog className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />{!compact && <span>{label}</span>}</>;
  const className = cn("inline-flex items-center gap-2 rounded-[var(--r-md)] px-2.5 py-2 text-[11px] font-medium text-[var(--text-muted)]", compact && "justify-center px-0");
  return developer
    ? <span className={className} title={label} aria-label={label}>{content}</span>
    : <Link href="/login" prefetch={false} className={className} title={label} aria-label={label}>{content}</Link>;
}
