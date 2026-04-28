"use client";

import { Calendar } from "lucide-react";
import { ComingSoonPage } from "@/components/coming-soon-page";

export default function SchedulePage() {
  return (
    <ComingSoonPage
      icon={Calendar}
      title="Schedule"
      description="Project timelines, milestones, and a Gantt-lite view will live here. Track critical path activities, dependencies, and team workload at a glance."
      eta="Day 12"
    />
  );
}
