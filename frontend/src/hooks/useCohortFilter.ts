"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  applyCohortFilterToSearchParams,
  buildCohortPatientIdSet,
  cohortFilterIsActive,
  parseCohortFilter,
  type CohortFilter,
} from "@/lib/cohortFilter";
import { parseSutHomeTab } from "@/lib/constants";
import type { PatientMeta } from "@/lib/domains/patient";

export function useCohortFilter() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filter = useMemo(() => parseCohortFilter(searchParams), [searchParams]);
  const isActive = cohortFilterIsActive(filter);
  const activeTab = parseSutHomeTab(searchParams.get("tab"));

  const setFilter = useCallback(
    (next: Partial<CohortFilter>) => {
      const params = new URLSearchParams(searchParams.toString());
      applyCohortFilterToSearchParams(params, { ...filter, ...next });
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [filter, pathname, router, searchParams],
  );

  const clearFilter = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    applyCohortFilterToSearchParams(params, {
      q: "",
      sex: "",
      ageMin: null,
      ageMax: null,
      doctor: "",
    });
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }, [pathname, router, searchParams]);

  return { filter, isActive, setFilter, clearFilter, activeTab };
}

export function useCohortPatientIds(patientMeta: PatientMeta[]) {
  const { filter, isActive } = useCohortFilter();

  return useMemo(() => {
    const ids = buildCohortPatientIdSet(patientMeta, filter);
    return {
      ids,
      count: ids.size,
      isActive,
      filter,
    };
  }, [filter, isActive, patientMeta]);
}
