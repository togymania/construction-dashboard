import { redirect } from "next/navigation";

/**
 * Legacy /workforce route. Workforce is now project-scoped — see
 * /projects/[id]/workforce. Bounce to the project picker.
 */
export default function LegacyWorkforceRedirect() {
  redirect("/projects");
}
