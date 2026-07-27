"use client";

import { useState, type FormEvent } from "react";
import BilunFullLogo from "@/components/brand/BilunFullLogo";
import { Button, inputClass } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

/**
 * Shared-password login screen.
 *
 * Posts credentials to /api/auth/login (proxied to the backend via the
 * next.config.ts rewrite). On success the backend sets the httpOnly
 * bilun:session cookie; a hard navigation then loads `/` so middleware
 * sees the cookie (soft router.replace can race the Set-Cookie commit).
 */
export default function LoginPage() {
  const t = useT();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, password }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || !body?.ok) {
        setError(
          res.status === 503
            ? t("auth.login.notConfigured")
            : t("auth.login.error"),
        );
        return;
      }
      // Hard navigation so the new Set-Cookie is always sent on the next
      // document request. router.replace() can race the cookie commit and
      // leave a fresh (e.g. Incognito) session stuck on /login with no error.
      window.location.assign("/");
      return;
    } catch {
      setError(t("auth.login.networkError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-[var(--surface-soft)] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-4 text-center">
          <BilunFullLogo size={28} />
          <div>
            <h1 className="sr-only">{t("auth.login.title")}</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              {t("auth.login.subtitle")}
            </p>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-base)] p-6 shadow-[var(--shadow-2)]"
        >
          <div className="space-y-1.5">
            <label
              htmlFor="username"
              className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]"
            >
              {t("auth.login.username")}
            </label>
            <input
              id="username"
              name="username"
              type="text"
              required
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={inputClass}
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="password"
              className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]"
            >
              {t("auth.login.password")}
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
          </div>

          {error && (
            <p className="rounded-md bg-[var(--danger-tint)] px-3 py-2 text-sm text-[var(--danger)]">
              {error}
            </p>
          )}

          <Button
            type="submit"
            variant="primary"
            disabled={submitting}
            className="w-full disabled:opacity-60"
          >
            {submitting ? t("auth.login.submitting") : t("auth.login.submit")}
          </Button>
        </form>
      </div>
    </main>
  );
}
