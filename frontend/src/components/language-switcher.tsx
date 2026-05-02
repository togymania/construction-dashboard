"use client";

/**
 * Language switcher (EN/TR) — wired to LanguageProvider.
 * Selecting a language updates the provider, which propagates new strings
 * everywhere components consume useT().
 */
import { Globe, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useT } from "@/lib/i18n/provider";
import type { Locale } from "@/lib/i18n/translations";

const LANGS: { code: Locale; label: string; flag: string }[] = [
  { code: "EN", label: "English", flag: "🇬🇧" },
  { code: "TR", label: "Türkçe", flag: "🇹🇷" },
];

export function LanguageSwitcher() {
  const { locale, setLocale, t, ready } = useT();

  // Until provider hydrates from localStorage, show "EN" so server and client
  // markup match (avoids hydration mismatch flicker).
  const display = ready ? locale : "EN";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 relative"
          aria-label={t("header.changeLanguage")}
          title={t("header.changeLanguage")}
        >
          <Globe className="h-4 w-4" />
          <span className="absolute -bottom-0.5 -right-0.5 text-[8px] font-bold tabular-nums px-0.5 rounded bg-indigo-500 text-white leading-tight">
            {display}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[160px]">
        {LANGS.map((l) => (
          <DropdownMenuItem
            key={l.code}
            onClick={() => setLocale(l.code)}
            className="flex items-center justify-between gap-2 cursor-pointer"
          >
            <span className="flex items-center gap-2">
              <span aria-hidden>{l.flag}</span>
              <span>{l.label}</span>
              <span className="text-xs text-muted-foreground">({l.code})</span>
            </span>
            {locale === l.code && <Check className="h-3.5 w-3.5 text-indigo-500" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
