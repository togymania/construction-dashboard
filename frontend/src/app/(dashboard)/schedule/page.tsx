import { redirect } from "next/navigation";

export default function LegacyScheduleRedirect() {
  redirect("/projects");
}
