"use client";

import Link from "next/link";
import { ArrowLeft, type LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n/provider";

interface Props {
  icon: LucideIcon;
  title: string;
  description: string;
  /** Sprint day or release window where this lands. */
  eta?: string;
}

/**
 * Polite placeholder for sidebar links whose feature is not built yet.
 * Premium look: large icon in a glass-tinted circle, big title, supportive copy.
 */
export function ComingSoonPage({ icon: Icon, title, description, eta }: Props) {
  const { t } = useT();
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <Card className="max-w-lg w-full">
        <CardContent className="pt-12 pb-10 text-center space-y-6">
          <div className="mx-auto w-20 h-20 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Icon className="h-9 w-9 text-primary" />
          </div>

          <div className="space-y-2">
            <h1 className="text-3xl font-heading font-bold tracking-tight">
              {title}
            </h1>
            <p className="text-sm uppercase tracking-[0.2em] text-primary/70 font-semibold">
              {t("pages.comingSoon")}
            </p>
          </div>

          <p className="text-muted-foreground max-w-sm mx-auto leading-relaxed">
            {description}
          </p>

          {eta && (
            <p className="text-xs text-muted-foreground/70 italic">
              {t("comingSoon.eta")}: {eta}
            </p>
          )}

          <Link href="/" className="inline-block pt-2">
            <Button variant="outline">
              <ArrowLeft className="h-4 w-4 mr-2" />
              {t("comingSoon.backToDashboard")}
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
