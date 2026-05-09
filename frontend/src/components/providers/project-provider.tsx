"use client";

import * as React from "react";
import { useEffect, useState, useCallback, createContext, useContext } from "react";

import { api, ApiError } from "@/lib/api-client";
import type { Project } from "@/types/project";

interface ProjectContextValue {
  project: Project | null;
  isLoading: boolean;
  error: string | null;
  /** Force-refetch the project from the API. */
  refresh: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

interface Props {
  projectId: number;
  children: React.ReactNode;
}

/**
 * Loads a single project by id and exposes it to all child pages
 * inside /projects/[id]/*. Pages can read `useProject()` to get the
 * current project without re-fetching.
 *
 * If the id is invalid or the user can't see the project, the context
 * surfaces an error string and the layout shows a friendly message.
 */
export function ProjectProvider({ projectId, children }: Props) {
  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.projects.get(projectId);
      setProject(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("Project not found");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load project");
      }
      setProject(null);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <ProjectContext.Provider value={{ project, isLoading, error, refresh }}>
      {children}
    </ProjectContext.Provider>
  );
}

/**
 * Read the current project. Throws if used outside ProjectProvider.
 *
 * Returns the full context (project, isLoading, error, refresh) so callers
 * can render skeletons or error states as needed.
 */
export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (ctx === null) {
    throw new Error("useProject must be used inside <ProjectProvider>");
  }
  return ctx;
}
