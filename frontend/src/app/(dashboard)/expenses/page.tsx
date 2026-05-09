import { redirect } from "next/navigation";

/**
 * Legacy /expenses route. Expenses are now project-scoped — see
 * /projects/[id]/expenses. Bounce to the project picker.
 */
export default function LegacyExpensesRedirect() {
  redirect("/projects");
}
