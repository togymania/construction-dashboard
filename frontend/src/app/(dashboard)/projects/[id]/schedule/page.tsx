"use client";

import { Calendar } from "lucide-react";
import { ComingSoonPage } from "@/components/coming-soon-page";
import { useT } from "@/lib/i18n/provider";

export default function ProjectSchedulePage() {
  const { t } = useT();
  return (
    <ComingSoonPage
      icon={Calendar}
      title={t("comingSoon.scheduleTitle")}
      description={t("comingSoon.scheduleDescription")}
      eta="Day 12"
    />
  );
}
