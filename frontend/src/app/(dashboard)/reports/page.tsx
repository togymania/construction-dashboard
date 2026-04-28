"use client";

import { FileBarChart } from "lucide-react";
import { ComingSoonPage } from "@/components/coming-soon-page";

export default function ReportsPage() {
  return (
    <ComingSoonPage
      icon={FileBarChart}
      title="Reports & Export"
      description="One-click Excel and PDF exports for budget, expenses, payments, and workforce data. Project summary reports for stakeholder reviews."
      eta="Day 13"
    />
  );
}
