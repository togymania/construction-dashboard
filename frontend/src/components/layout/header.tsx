"use client";

import { Bell, Search, LogOut, User as UserIcon } from "lucide-react";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";
import { useUser } from "@/components/providers/user-provider";
import { useT } from "@/lib/i18n/provider";

function isDynamicSegment(s: string): boolean {
  // Treat numeric IDs and UUID-like strings as dynamic — not human-readable.
  return /^\\d+$/.test(s) || /^[0-9a-f]{8}-[0-9a-f]{4}/i.test(s);
}

function prettify(s: string): string {
  return s
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function getBreadcrumbTranslated(
  pathname: string,
  t: (k: string) => string,
): string {
  // Map first segment to its translated nav label when possible
  if (pathname === "/") return t("nav.dashboard");
  const first = pathname.split("/").filter(Boolean)[0];
  const navMap: Record<string, string> = {
    projects: "nav.projects",
    subcontractors: "nav.subcontractors",
    workforce: "nav.workforce",
    schedule: "nav.schedule",
    risks: "nav.risks",
    reports: "nav.reports",
    settings: "nav.settings",
  };
  if (first && navMap[first]) return t(navMap[first]);
  return getBreadcrumb(pathname);
}

function getBreadcrumb(pathname: string): string {
  if (pathname === "/") return "Dashboard";
  const segments = pathname.split("/").filter(Boolean);
  // Walk from the end and pick the last non-dynamic segment as the title.
  // /subcontractors/1                  -> "Subcontractors"
  // /projects/1/budget                 -> "Budget"
  // /subcontractors/1/contracts/3      -> "Contracts"
  // /settings/budget-categories        -> "Budget Categories"
  for (let i = segments.length - 1; i >= 0; i--) {
    if (!isDynamicSegment(segments[i])) {
      return prettify(segments[i]);
    }
  }
  return prettify(segments[0] ?? "");
}

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

export function Header() {
  const pathname = usePathname();
  const { user, logout } = useUser();
  const { t } = useT();
  const title = getBreadcrumbTranslated(pathname, t);

  const displayName = user?.full_name ?? t("status.loading");
  const displayRole = user ? formatRole(user.role) : "";
  const initials = user ? getInitials(user.full_name) : "?";

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-6">
      <div className="flex-1">
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
      </div>

      <div className="hidden md:block">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder={t("header.search")}
            className="w-64 pl-8 bg-card/50 backdrop-blur-sm border-foreground/8 dark:border-white/8 focus-visible:ring-primary/50 focus-visible:ring-2 transition-all"
          />
        </div>
      </div>

      <Button variant="outline" size="icon" className="relative bg-card/50 backdrop-blur-sm border-foreground/8 dark:border-white/8 hover:bg-primary/10 hover:border-primary/30 transition-all">
        <Bell className="h-4 w-4" />
        <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] text-destructive-foreground shadow-[0_0_8px_rgba(239,68,68,0.5)]">
          3
        </span>
        <span className="sr-only">{t("header.notifications")}</span>
      </Button>

      <LanguageSwitcher />

      <ThemeToggle />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="relative h-9 w-9 rounded-full">
            <Avatar className="h-9 w-9">
              <AvatarFallback>{initials}</AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>
            <div className="flex flex-col">
              <span className="text-sm font-medium">{displayName}</span>
              <span className="text-xs text-muted-foreground font-normal">
                {user?.email}
              </span>
              {displayRole && (
                <span className="text-xs text-muted-foreground font-normal mt-0.5">
                  {displayRole}
                </span>
              )}
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem>
            <UserIcon className="mr-2 h-4 w-4" />
            {t("header.profile")}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout} className="text-destructive focus:text-destructive">
            <LogOut className="mr-2 h-4 w-4" />
            {t("nav.logout")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
