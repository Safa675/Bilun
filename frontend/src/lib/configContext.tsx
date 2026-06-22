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

/** Default fallback config used while loading or on error. */
const FALLBACK_CONFIG: FrontendConfig = {
  risk_tiers: [
    { min: 70, key: "dusuk", label: "Low Risk", color: theme.accent },
    { min: 40, key: "orta", label: "Moderate", color: "#B45309" },
    { min: 20, key: "yuksek", label: "High", color: "#B45309" },
    { min: 0, key: "kritik", label: "Critical", color: "#B91C1C" },
  ],
  rating_tiers: [],
  subscores: {},
  directions: {
    rapidly_declining: { arrow: "\u21CA", color: "#B91C1C", label: "Rapidly Declining" },
    declining: { arrow: "\u2198", color: "#B45309", label: "Declining" },
    stable: { arrow: "\u2192", color: theme.accent, label: "Stable" },
    improving: { arrow: "\u2197", color: theme.accent, label: "Improving" },
    insufficient_data: { arrow: "\u2015", color: "#A1A1AA", label: "Insufficient Data" },
    exitus: { arrow: "\u2020", color: "#A1A1AA", label: "Exitus" },
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
    label: "SUT data source unavailable",
    is_synthetic: null,
    notice: "SUT data-source provenance has not loaded yet.",
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
        const res = await fetch(`${resolveApiBase()}/api/frontend-config`);
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
