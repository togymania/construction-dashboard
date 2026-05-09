import { ProjectProvider } from "@/components/providers/project-provider";
import { ProjectSidebar } from "@/components/layout/project-sidebar";

interface Props {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}

/**
 * Layout that wraps every page under /projects/[id]/*.
 *
 * Renders a project-scoped sub-sidebar (Overview / Subcontractors /
 * Workforce / Budget / Expenses / Schedule / Risks / Reports) and
 * exposes the current project via ProjectProvider so child pages can
 * call useProject() without re-fetching.
 *
 * The outer DashboardLayout already renders the global Sidebar +
 * Header. We slot this sub-sidebar in as the first column of the main
 * content area so the global nav stays visible on the far left.
 */
export default async function ProjectLayout({ children, params }: Props) {
  const { id } = await params;
  const projectId = Number(id);

  return (
    <ProjectProvider projectId={projectId}>
      <div className="flex flex-1 min-h-[calc(100vh-4rem)] -m-6">
        <ProjectSidebar projectId={projectId} className="hidden md:flex" />
        <div className="flex-1 p-6 overflow-x-auto">{children}</div>
      </div>
    </ProjectProvider>
  );
}
