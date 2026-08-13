"use client";

/**
 * ConfigProvider — fetches /api/frontend-config once on mount and
 * provides all domain constants to the component tree via useConfig().
 *
 * Components that need risk tiers, subscore weights, direction labels,
 * performance metrics, etc. call useConfig() instead of hardcoding.
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { FrontendConfig } from "./configTypes";
import { theme } from "@/lib/theme";

interface ConfigState {
  config: FrontendConfig | null;
  loading: boolean;
  error: string | null;
}

const ConfigContext = createContext<ConfigState>({
  config: null,
  loading: true,
  error: null,
});

/** Default fallback config used while loading or on error.
 *
 * Display strings (risk-tier labels, direction labels, sut_data_source
 * label/notice) are intentionally empty: the fallback represents an
 * unavailable/uninitialized state, and the only config consumers
 * (AppSidebar via SyntheticDemoChip, SUTOptimizerTab via regulatory
 * counts) never render these label fields. The real localized labels
 * come from the backend /api/frontend-config response in production.
 */
const FALLBACK_CONFIG: FrontendConfig = {
  risk_tiers: [
    { min: 70, key: "dusuk", label: "", color: theme.accent },
    { min: 40, key: "orta", label: "", color: "#B45309" },
    { min: 20, key: "yuksek", label: "", color: "#B45309" },
    { min: 0, key: "kritik", label: "", color: "#B91C1C" },
  ],
  rating_tiers: [],
  subscores: {},
  directions: {
    rapidly_declining: { arrow: "\u21CA", color: "#B91C1C", label: "" },
    declining: { arrow: "\u2198", color: "#B45309", label: "" },
    stable: { arrow: "\u2192", color: theme.accent, label: "" },
    improving: { arrow: "\u2197", color: theme.accent, label: "" },
    insufficient_data: { arrow: "\u2015", color: "#A1A1AA", label: "" },
    exitus: { arrow: "\u2020", color: "#A1A1AA", label: "" },
  },
  regime_states: {},
  performance: {
    active_model: null,
  },
  regulatory: {
    ek1a_exemption_count: 0,
    ek2g_procedure_count: 0,
    ek2c1_procedure_count: 0,
  },
  cost_tiers: [],
  sut_data_source: {
    mode: "unavailable",
    label: "",
    is_synthetic: null,
    notice: "",
    unavailable_reason: "frontend_config_unavailable",
    required_inputs_missing: ["sut_data_source"],
  },
};

function resolveApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window === "undefined") return "http://localhost:8000";
  return "";
}

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ConfigState>({
    config: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(`${resolveApiBase()}/api/frontend-config`, {
          credentials: "include",
        });
        if (!res.ok) throw new Error(`Config fetch failed: ${res.status}`);
        const data: FrontendConfig = await res.json();
        if (!cancelled) setState({ config: data, loading: false, error: null });
      } catch (e) {
        if (!cancelled) {
          setState({
            config: FALLBACK_CONFIG,
            loading: false,
            error: e instanceof Error ? e.message : "Unknown error",
          });
        }
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  return (
    <ConfigContext.Provider value={state}>
      {children}
    </ConfigContext.Provider>
  );
}

/**
 * Access the frontend config from any component.
 *
 * Returns FALLBACK_CONFIG while loading or on error,
 * so consumers always get a usable config object.
 */
export function useConfig(): FrontendConfig {
  const { config } = useContext(ConfigContext);
  return config ?? FALLBACK_CONFIG;
}
