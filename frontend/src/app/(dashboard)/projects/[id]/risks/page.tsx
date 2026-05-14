"use client";

import { AlertTriangle } from "lucide-react";
import { ComingSoonPage } from "@/components/coming-soon-page";
import { useT } from "@/lib/i18n/provider";

export default function ProjectRisksPage() {
  const { t } = useT();
  return (
    <ComingSoonPage
      icon={AlertTriangle}
      title={t("comingSoon.risksTitle")}
      description={t("comingSoon.risksDescription")}
      eta="Day 12+"
    />
  );
}
