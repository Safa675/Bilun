"use client";

import { useEffect, useState, type FormEvent } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Info,
  Loader2,
  Mail,
  MessageSquareWarning,
  Send,
  X,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/useTranslations";
import { useUserRole } from "@/components/shell/RoleProvider";

interface ReportProblemModalProps {
  open: boolean;
  onClose: () => void;
}

type FeedbackCategory = "bug" | "sut" | "feature" | "general";

export default function ReportProblemModal({ open, onClose }: ReportProblemModalProps) {
  const t = useT();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const userRole = useUserRole();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [category, setCategory] = useState<FeedbackCategory>("bug");
  const [message, setMessage] = useState("");
  const [includeContext, setIncludeContext] = useState(true);
  const [websiteHoneypot, setWebsiteHoneypot] = useState("");

  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "local_only" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [serverMailtoHref, setServerMailtoHref] = useState("");

  const activeTab = searchParams.get("tab") || "patients";
  const currentUrl = typeof window !== "undefined" ? window.location.href : pathname;

  useEffect(() => {
    if (open) {
      setStatus("idle");
      setErrorMessage("");
      setServerMailtoHref("");
    }
  }, [open]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const mailtoSubject = encodeURIComponent(t("shell.feedback.mailtoSubject", {
    category: t(`shell.feedback.categories.${category}`),
    name: name || t("shell.feedback.anonymousUser"),
  }));
  const mailtoBody = encodeURIComponent(
    t("shell.feedback.mailtoBody", {
      name, email, category: t(`shell.feedback.categories.${category}`),
      tab: activeTab, url: currentUrl, role: userRole, message,
    }),
  );
  const clientMailtoHref = `mailto:safaoksuz@bilun.tech?subject=${mailtoSubject}&body=${mailtoBody}`;
  const effectiveMailtoHref = serverMailtoHref || clientMailtoHref;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !message.trim()) {
      return;
    }

    setStatus("submitting");
    setErrorMessage("");

    try {
      const payload = {
        name: name.trim(),
        email: email.trim(),
        category,
        message: message.trim(),
        website: websiteHoneypot,
        systemInfo: includeContext
          ? {
              activeTab,
              role: userRole,
              url: currentUrl,
              timestamp: new Date().toISOString(),
            }
          : undefined,
      };

      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.mailtoHref) setServerMailtoHref(data.mailtoHref);
        throw new Error(data.error || t("shell.feedback.errorTitle"));
      }

      if (data.delivered === false) {
        if (data.mailtoHref) setServerMailtoHref(data.mailtoHref);
        setStatus("local_only");
      } else {
        setStatus("success");
      }
    } catch (err: any) {
      console.error("Feedback submit failed:", err);
      setStatus("error");
      setErrorMessage(err.message || t("shell.feedback.errorTitle"));
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="feedback-modal-title"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-[color-mix(in_srgb,var(--text-primary)_60%,transparent)] backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Card */}
      <div className="relative w-full max-w-lg overflow-hidden rounded-[var(--r-lg)] border border-[var(--border-subtle)] bg-[var(--surface-base)] shadow-[var(--shadow-3)] transition-all">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--gold-subtle)] text-[var(--gold)]">
              <MessageSquareWarning className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <h2
                id="feedback-modal-title"
                className="text-sm font-semibold text-[var(--text-primary)]"
              >
                {t("shell.feedback.title")}
              </h2>
              <p className="text-xs text-[var(--text-muted)]">
                safaoksuz@bilun.tech
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("shell.feedback.close")}
            className="inline-flex h-7 w-7 items-center justify-center rounded-[var(--r-md)] text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-primary)] transition-colors"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5">
          {status === "success" ? (
            <div className="flex flex-col items-center py-6 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--emerald-subtle)] text-[var(--emerald)]">
                <CheckCircle2 className="h-6 w-6" aria-hidden="true" />
              </div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">
                {t("shell.feedback.successTitle")}
              </h3>
              <p className="mt-1.5 max-w-sm text-xs text-[var(--text-muted)]">
                {t("shell.feedback.successDescription")}
              </p>
              <button
                type="button"
                onClick={onClose}
                className="mt-6 inline-flex items-center justify-center rounded-[var(--r-md)] bg-[var(--surface-tint)] px-4 py-2 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-base)] border border-[var(--border-subtle)] transition-colors"
              >
                {t("shell.feedback.close")}
              </button>
            </div>
          ) : status === "local_only" ? (
            <div className="flex flex-col items-center py-4 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--gold-subtle)] text-[var(--gold)]">
                <Info className="h-6 w-6" aria-hidden="true" />
              </div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">
                {t("shell.feedback.localOnlyTitle")}
              </h3>
              <p className="mt-2 max-w-md text-xs text-[var(--text-secondary)] leading-relaxed">
                {t("shell.feedback.localOnlyDescription")}
              </p>
              <p className="mt-1 max-w-md text-xs text-[var(--text-muted)]">
                {t("shell.feedback.localOnlyFallback")}
              </p>
              <div className="mt-5 flex items-center gap-3">
                <a
                  href={effectiveMailtoHref}
                  className="inline-flex items-center gap-1.5 rounded-[var(--r-md)] bg-[var(--gold)] px-4 py-2 text-xs font-medium text-[var(--text-inverse)] hover:bg-[var(--gold-hover)] transition-all"
                >
                  <Mail className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{t("shell.feedback.directEmailButton")}</span>
                  <ExternalLink className="h-3 w-3 opacity-70" aria-hidden="true" />
                </a>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-[var(--r-md)] bg-[var(--surface-tint)] border border-[var(--border-subtle)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                >
                  {t("shell.feedback.close")}
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <p className="text-xs text-[var(--text-muted)]">
                {t("shell.feedback.description")}
              </p>

              {/* Honeypot for bots */}
              <div aria-hidden="true" className="absolute left-[-9999px] h-0 w-0 overflow-hidden">
                <label htmlFor="feedback-website">Website</label>
                <input
                  id="feedback-website"
                  type="text"
                  name="website"
                  tabIndex={-1}
                  value={websiteHoneypot}
                  onChange={(e) => setWebsiteHoneypot(e.target.value)}
                  autoComplete="off"
                />
              </div>

              {/* Name & Email Grid */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="feedback-name"
                    className="mb-1 block text-xs font-medium text-[var(--text-secondary)]"
                  >
                    {t("shell.feedback.nameLabel")} <span className="text-[var(--rose)]">*</span>
                  </label>
                  <input
                    id="feedback-name"
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={t("shell.feedback.namePlaceholder")}
                    className="w-full rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-tint)] px-3 py-2 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--gold)] focus:outline-hidden focus:ring-1 focus:ring-[var(--gold)]"
                  />
                </div>

                <div>
                  <label
                    htmlFor="feedback-email"
                    className="mb-1 block text-xs font-medium text-[var(--text-secondary)]"
                  >
                    {t("shell.feedback.emailLabel")} <span className="text-[var(--rose)]">*</span>
                  </label>
                  <input
                    id="feedback-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={t("shell.feedback.emailPlaceholder")}
                    className="w-full rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-tint)] px-3 py-2 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--gold)] focus:outline-hidden focus:ring-1 focus:ring-[var(--gold)]"
                  />
                </div>
              </div>

              {/* Category */}
              <div>
                <label
                  htmlFor="feedback-category"
                  className="mb-1 block text-xs font-medium text-[var(--text-secondary)]"
                >
                  {t("shell.feedback.categoryLabel")}
                </label>
                <select
                  id="feedback-category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value as FeedbackCategory)}
                  className="w-full rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-tint)] px-3 py-2 text-xs text-[var(--text-primary)] focus:border-[var(--gold)] focus:outline-hidden focus:ring-1 focus:ring-[var(--gold)]"
                >
                  <option value="bug">{t("shell.feedback.categories.bug")}</option>
                  <option value="sut">{t("shell.feedback.categories.sut")}</option>
                  <option value="feature">{t("shell.feedback.categories.feature")}</option>
                  <option value="general">{t("shell.feedback.categories.general")}</option>
                </select>
              </div>

              {/* Message */}
              <div>
                <label
                  htmlFor="feedback-message"
                  className="mb-1 block text-xs font-medium text-[var(--text-secondary)]"
                >
                  {t("shell.feedback.messageLabel")} <span className="text-[var(--rose)]">*</span>
                </label>
                <textarea
                  id="feedback-message"
                  rows={4}
                  required
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder={t("shell.feedback.messagePlaceholder")}
                  className="w-full resize-y rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-tint)] px-3 py-2 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--gold)] focus:outline-hidden focus:ring-1 focus:ring-[var(--gold)]"
                />
              </div>

              {/* System Context Toggle */}
              <div className="flex items-center gap-2">
                <input
                  id="feedback-context"
                  type="checkbox"
                  checked={includeContext}
                  onChange={(e) => setIncludeContext(e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-[var(--border-subtle)] text-[var(--gold)] focus:ring-[var(--gold)]"
                />
                <label
                  htmlFor="feedback-context"
                  className="text-xs text-[var(--text-muted)] cursor-pointer select-none"
                >
                  {t("shell.feedback.systemInfoLabel")} ({activeTab} · {userRole})
                </label>
              </div>

              {/* Error Box with Direct Email Fallback */}
              {status === "error" && (
                <div className="rounded-[var(--r-md)] border border-[var(--rose-subtle)] bg-[var(--rose-subtle)]/20 p-3 text-xs text-[var(--rose)]">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                    <div className="flex-1">
                      <p className="font-semibold">{errorMessage}</p>
                      <p className="mt-1 text-xs text-[var(--text-secondary)]">
                        {t("shell.feedback.errorFallback")}
                      </p>
                      <a
                        href={effectiveMailtoHref}
                        className="mt-2 inline-flex items-center gap-1.5 rounded bg-[var(--surface-base)] border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--gold)] transition-colors"
                      >
                        <Mail className="h-3 w-3" aria-hidden="true" />
                        {t("shell.feedback.directEmailButton")} (safaoksuz@bilun.tech)
                      </a>
                    </div>
                  </div>
                </div>
              )}

              {/* Footer Actions */}
              <div className="mt-2 flex items-center justify-end gap-2 border-t border-[var(--border-subtle)] pt-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-[var(--r-md)] px-3 py-1.5 text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-secondary)] transition-colors"
                >
                  {t("shell.feedback.close")}
                </button>
                <button
                  type="submit"
                  disabled={status === "submitting" || !name.trim() || !email.trim() || !message.trim()}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-[var(--r-md)] px-4 py-1.5 text-xs font-medium text-[var(--text-inverse)] transition-all",
                    "bg-[var(--gold)] hover:bg-[var(--gold-hover)] active:scale-95 disabled:opacity-50 disabled:pointer-events-none",
                  )}
                >
                  {status === "submitting" ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                      <span>{t("shell.feedback.submitting")}</span>
                    </>
                  ) : (
                    <>
                      <Send className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>{t("shell.feedback.submitButton")}</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
