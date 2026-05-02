"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { translations, SUPPORTED_LOCALES, type Locale } from "./translations";

const STORAGE_KEY = "ui-lang-preference";

interface I18nContextValue {
  locale: Locale;
  setLocale: (next: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  ready: boolean;
}

const I18nContext = createContext<I18nContextValue>({
  locale: "EN",
  setLocale: () => {},
  t: (key) => key,
  ready: false,
});

/**
 * Resolve a dotted key against a nested object. Falls back to EN if missing,
 * then to the raw key as last resort. Variables in {curly} are interpolated.
 */
function resolve(
  locale: Locale,
  key: string,
  vars?: Record<string, string | number>,
): string {
  const parts = key.split(".");
  // Try requested locale first
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let cursor: any = translations[locale];
  for (const p of parts) {
    if (cursor && typeof cursor === "object" && p in cursor) cursor = cursor[p];
    else { cursor = undefined; break; }
  }

  // Fallback to EN
  if (cursor === undefined && locale !== "EN") {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let fb: any = translations.EN;
    for (const p of parts) {
      if (fb && typeof fb === "object" && p in fb) fb = fb[p];
      else { fb = undefined; break; }
    }
    cursor = fb;
  }

  if (typeof cursor !== "string") return key;

  // Interpolate {var} placeholders
  if (vars) {
    return cursor.replace(/\{(\w+)\}/g, (m, name) =>
      name in vars ? String(vars[name]) : m
    );
  }
  return cursor;
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  // Server-render with EN. Client may swap on hydration if user picked TR.
  const [locale, setLocaleState] = useState<Locale>("EN");
  const [ready, setReady] = useState(false);

  // Hydrate from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && (SUPPORTED_LOCALES as string[]).includes(saved)) {
        setLocaleState(saved as Locale);
      }
    } catch {
      // localStorage unavailable — keep default
    }
    setReady(true);
  }, []);

  // Reflect locale on <html lang>
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = locale.toLowerCase();
    }
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* ignore */ }
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => resolve(locale, key, vars),
    [locale],
  );

  const value = useMemo<I18nContextValue>(
    () => ({ locale, setLocale, t, ready }),
    [locale, setLocale, t, ready],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/** Use translations + locale state inside any client component. */
export function useT() {
  return useContext(I18nContext);
}
