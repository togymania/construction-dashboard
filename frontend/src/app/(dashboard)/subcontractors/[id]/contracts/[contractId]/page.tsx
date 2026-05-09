import { redirect } from "next/navigation";

export default function LegacyContractDetailRedirect() {
  redirect("/projects");
}
