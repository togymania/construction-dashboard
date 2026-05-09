import { redirect } from "next/navigation";

export default function LegacyRisksRedirect() {
  redirect("/projects");
}
