"use client";

import { AlertTriangle } from "lucide-react";
import { ComingSoonPage } from "@/components/coming-soon-page";

export default function RisksPage() {
  return (
    <ComingSoonPage
      icon={AlertTriangle}
      title="Risk Register"
      description="Centralized risk tracking with severity ratings, mitigation plans, and ownership. Stay ahead of issues before they impact delivery."
      eta="Day 12+"
    />
  );
}
