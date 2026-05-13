"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Briefcase,
  Settings,
  Tags,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useUser } from "@/components/providers/user-provider";
import { useT } from "@/lib/i18n/provider";

// `tKey` is the i18n key; `name` is a fallback used only if t() misses.
// Top-level navigation is intentionally minimal: Dashboard + Projects.
// Module pages (Subcontractors / Workforce / Expenses / Schedule / Risks / Reports)
// are project-scoped and live under /projects/[id]/* — see ProjectSidebar.
const navigation = [
  { tKey: "nav.dashboard", name: "Dashboard", href: "/", icon: LayoutDashboard },
  { tKey: "nav.projects", name: "Projects", href: "/projects", icon: Briefcase },
];

const adminNavigation = [
  {
    tKey: "nav.budgetCategories",
    name: "Budget Categories",
    href: "/settings/budget-categories",
    icon: Tags,
    requiredRoles: ["admin", "project_manager"] as const,
  },
];

const STORAGE_KEY = "ch.sidebar.collapsed";

function getInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function formatRole(role: string): string {
  return role
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/**
 * Read the persisted collapsed pref. We use a module-level read once on
 * mount; further updates are state-driven.
 */
function readPersistedCollapsed(): boolean | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (raw === "true") return true;
  if (raw === "false") return false;
  return null;
}

export function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname();
  const { user } = useUser();
  const { t } = useT();

  // Auto-collapse heuristic: when inside a project, default to collapsed
  // so the project sub-sidebar gets more room. Manual toggle overrides
  // this for the lifetime of the localStorage entry.
  const isInProject = /^\/projects\/\d+/.test(pathname);

  const [collapsed, setCollapsed] = React.useState<boolean>(isInProject);
  const [hydrated, setHydrated] = React.useState(false);

  // Hydrate once on mount: prefer persisted value, otherwise fall back to
  // the route-based heuristic.
  React.useEffect(() => {
    const persisted = readPersistedCollapsed();
    setCollapsed(persisted ?? isInProject);
    setHydrated(true);
    // We deliberately don't depend on isInProject — only initial route matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When the user navigates *into* a project from outside, soft-collapse if
  // they haven't explicitly set a pref yet. If they have a pref, respect it.
  React.useEffect(() => {
    if (!hydrated) return;
    if (readPersistedCollapsed() === null) {
      setCollapsed(isInProject);
    }
  }, [isInProject, hydrated]);

  function toggle() {
    setCollapsed((c) => {
      const next = !c;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_KEY, String(next));
      }
      return next;
    });
  }

  const visibleAdminLinks = adminNavigation.filter(
    (item) => user && (item.requiredRoles as readonly string[]).includes(user.role)
  );

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r bg-sidebar text-sidebar-foreground transition-[width] duration-200 ease-in-out",
        collapsed ? "w-14" : "w-64",
        className
      )}
    >
      {/* Brand row + collapse toggle — beyaz zemin, logo'nun kendi beyaz
          background'iyle sorunsuz birleşir; dark mode'da hafif kart tonu */}
      <div
        className={cn(
          "flex h-20 items-center border-b bg-white dark:bg-card",
          collapsed ? "justify-center px-2" : "justify-between px-4"
        )}
      >
        {collapsed ? (
          <button
            type="button"
            onClick={toggle}
            title="Monotekstroy — Expand sidebar"
            aria-label="Expand sidebar"
            className="relative flex h-12 w-12 items-center justify-center overflow-hidden rounded-md hover:bg-primary/10 transition-colors"
          >
            {/* Tam logoyu yerleştir, container w-12 ile kırparak sadece sembol kısmı görünür */}
            <Image
              src="/monotekstroy-logo.png"
              alt="Monotekstroy"
              width={144}
              height={48}
              priority
              className="h-12 w-auto max-w-none"
              style={{ objectFit: "contain", objectPosition: "left center" }}
            />
          </button>
        ) : (
          <>
            <Link href="/" className="flex items-center min-w-0" aria-label="Monotekstroy">
              <Image
                src="/monotekstroy-logo.png"
                alt="Monotekstroy"
                width={240}
                height={64}
                priority
                className="h-14 w-auto"
              />
            </Link>
            <button
              type="button"
              onClick={toggle}
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-primary/10 hover:text-foreground transition-colors"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      {/* Main nav */}
      <nav className={cn("flex-1 space-y-1", collapsed ? "p-2" : "p-3")}>
        {navigation.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          const Icon = item.icon;
          const label = t(item.tKey) || item.name;

          return (
            <Link
              key={item.name}
              href={item.href}
              title={collapsed ? label : undefined}
              className={cn(
                "group relative flex items-center rounded-md text-sm font-medium transition-all duration-300",
                "before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:rounded-r-full before:transition-all before:duration-300",
                collapsed ? "justify-center h-10 w-10 mx-auto" : "gap-3 px-3 py-2",
                isActive
                  ? "bg-primary/10 text-foreground before:h-6 before:w-[3px] before:bg-primary before:shadow-[0_0_12px_rgba(99,102,241,0.6)]"
                  : "text-muted-foreground hover:bg-primary/5 hover:text-foreground before:h-0 before:w-[3px] before:bg-transparent"
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 transition-colors duration-300",
                  isActive && "text-primary"
                )}
              />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}

        {visibleAdminLinks.length > 0 && (
          <>
            {!collapsed && (
              <div className="pt-4 pb-1">
                <p className="px-3 text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-[0.2em]">
                  Admin
                </p>
              </div>
            )}
            {collapsed && <div className="my-2 mx-2 border-t border-border/40" />}
            {visibleAdminLinks.map((item) => {
              const isActive = pathname.startsWith(item.href);
              const Icon = item.icon;
              const label = t(item.tKey) || item.name;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  title={collapsed ? label : undefined}
                  className={cn(
                    "group relative flex items-center rounded-md text-sm font-medium transition-all duration-300",
                    "before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:rounded-r-full before:transition-all before:duration-300",
                    collapsed ? "justify-center h-10 w-10 mx-auto" : "gap-3 px-3 py-2",
                    isActive
                      ? "bg-primary/10 text-foreground before:h-6 before:w-[3px] before:bg-primary before:shadow-[0_0_12px_rgba(99,102,241,0.6)]"
                      : "text-muted-foreground hover:bg-primary/5 hover:text-foreground before:h-0 before:w-[3px] before:bg-transparent"
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 transition-colors duration-300",
                      isActive && "text-primary"
                    )}
                  />
                  {!collapsed && <span>{label}</span>}
                </Link>
              );
            })}
          </>
        )}
      </nav>

      <Separator />

      {/* Footer: settings + user */}
      <div className={cn("space-y-1", collapsed ? "p-2" : "p-3")}>
        <Link
          href="/settings"
          title={collapsed ? "Settings" : undefined}
          className={cn(
            "group flex items-center rounded-md text-sm font-medium text-muted-foreground transition-all duration-300 hover:bg-primary/5 hover:text-foreground",
            collapsed ? "justify-center h-10 w-10 mx-auto" : "gap-3 px-3 py-2"
          )}
        >
          <Settings className="h-4 w-4 transition-colors duration-300 group-hover:text-primary" />
          {!collapsed && "Settings"}
        </Link>

        <div
          className={cn(
            "flex items-center rounded-md",
            collapsed ? "justify-center p-1" : "gap-3 px-3 py-2"
          )}
          title={
            collapsed && user
              ? `${user.full_name} · ${formatRole(user.role)}`
              : undefined
          }
        >
          <Avatar className="h-8 w-8">
            <AvatarFallback>{user ? getInitials(user.full_name) : "?"}</AvatarFallback>
          </Avatar>
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-medium truncate">
                {user?.full_name ?? "Loading..."}
              </span>
              <span className="text-xs text-muted-foreground truncate">
                {user ? formatRole(user.role) : ""}
              </span>
            </div>
          )}
        </div>

        {collapsed && (
          <button
            type="button"
            onClick={toggle}
            title="Expand sidebar"
            className="mt-1 flex h-9 w-9 mx-auto items-center justify-center rounded-md text-muted-foreground hover:bg-primary/10 hover:text-foreground transition-colors"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
        )}
      </div>
    </aside>
  );
}
