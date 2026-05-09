import { redirect } from "next/navigation";

export default function LegacyReportsRedirect() {
  redirect("/projects");
}
