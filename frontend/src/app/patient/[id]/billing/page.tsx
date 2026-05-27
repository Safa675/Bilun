"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { buildSutPatientHref } from "@/lib/constants";

export default function SutPatientBillingRedirectPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const patientId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? "";

  useEffect(() => {
    if (patientId) {
      router.push(buildSutPatientHref(patientId));
    }
  }, [patientId, router]);

  return null;
}
