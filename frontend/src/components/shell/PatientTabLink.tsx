"use client";

import { useState, type CSSProperties, type MouseEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { buildSutPatientHref } from "@/lib/constants";
import {
  backgroundOpenKind,
  isBackgroundTabPointer,
  patientViewFromHref,
} from "@/lib/patientTabOpen";
import { useT } from "@/lib/i18n/useTranslations";
import { useWorkspaceStoreApi } from "@/stores/workspaceContext";

export function PatientTabContextMenu({
  x,
  y,
  onOpen,
  onDismiss,
}: {
  x: number;
  y: number;
  onOpen: () => void;
  onDismiss: () => void;
}) {
  const t = useT();
  const stop = (event: { preventDefault: () => void; stopPropagation: () => void }) => {
    event.preventDefault();
    event.stopPropagation();
  };
  const menu = (
    <>
      <button
        type="button"
        aria-hidden="true"
        tabIndex={-1}
        className="fixed inset-0 z-[70] cursor-default"
        onMouseDown={stop}
        onClick={(event) => {
          stop(event);
          onDismiss();
        }}
        onContextMenu={(event) => {
          stop(event);
          onDismiss();
        }}
      />
      <div
        role="menu"
        data-patient-tab-menu
        className="fixed z-[80] min-w-40 rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] p-1 shadow-[var(--shadow-2)]"
        style={{ left: x, top: y }}
      >
        <button
          type="button"
          role="menuitem"
          onMouseDown={(event) => {
            stop(event);
            onOpen();
          }}
          onClick={(event) => {
            stop(event);
            onDismiss();
          }}
          className="w-full rounded-[var(--r-sm)] px-2.5 py-1.5 text-left text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-tint)]"
        >
          {t("shell.workspaceTabs.openInNewTab")}
        </button>
      </div>
    </>
  );
  if (typeof document === "undefined") return menu;
  return createPortal(menu, document.body);
}

export function useOpenPatientBackground() {
  const store = useWorkspaceStoreApi();
  const router = useRouter();
  return (patientId: string, href?: string) => {
    const resolved = href ?? buildSutPatientHref(patientId);
    const view = patientViewFromHref(resolved, patientId);
    if (backgroundOpenKind(store.getState().tabs, view) === "switch") {
      router.push(resolved);
      return;
    }
    store.getState().openBackground(view);
  };
}

export default function PatientTabLink({
  patientId,
  href,
  className,
  style,
  children,
  onClick,
}: {
  patientId: string;
  href?: string;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
  onClick?: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const resolved = href ?? buildSutPatientHref(patientId);
  const openBackground = useOpenPatientBackground();
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);

  const openInStrip = () => {
    openBackground(patientId, resolved);
  };

  return (
    <>
      <Link
        href={resolved}
        scroll={false}
        data-patient-tab-link={patientId}
        className={className}
        style={style}
        onClick={(event) => {
          onClick?.(event);
          if (event.defaultPrevented) return;
          if (isBackgroundTabPointer(event)) {
            event.preventDefault();
            openInStrip();
          }
        }}
        onAuxClick={(event) => {
          if (event.button !== 1) return;
          event.preventDefault();
          event.stopPropagation();
          openInStrip();
        }}
        onContextMenu={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setMenu({ x: event.clientX, y: event.clientY });
        }}
      >
        {children}
      </Link>
      {menu ? (
        <PatientTabContextMenu
          x={menu.x}
          y={menu.y}
          onOpen={openInStrip}
          onDismiss={() => setMenu(null)}
        />
      ) : null}
    </>
  );
}
