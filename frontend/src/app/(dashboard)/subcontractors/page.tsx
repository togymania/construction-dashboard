import { redirect } from "next/navigation";

/**
 * The legacy /subcontractors route. Subcontractors are now project-scoped
 * — see /projects/[id]/subcontractors. We bounce visitors to the project
 * picker so they can pick a project context first.
 */
export default function LegacySubcontractorsRedirect() {
  redirect("/projects");
}
