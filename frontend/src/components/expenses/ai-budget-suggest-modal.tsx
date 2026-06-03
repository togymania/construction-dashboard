"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, X, Globe, Sparkles, Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api-client";
import type { MatchSuggestion } from "@/types/reconciliation";

type RowState = "pending" | "approved" | "rejected" | "busy";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  suggestions: MatchSuggestion[];
  loading?: boolean;
  onResolved?: () => void;
}

function confidencePct(score: number | string): number {
  const n = typeof score === "string" ? parseFloat(score) : score;
  return Number.isFinite(n) ? Math.round(n) : 0;
}

function confidenceColor(pct: number): string {
  if (pct >= 90) return "text-emerald-600";
  if (pct >= 75) return "text-amber-600";
  return "text-muted-foreground";
}

export function AiBudgetSuggestModal({
  open,
  onOpenChange,
  suggestions,
  loading = false,
  onResolved,
}: Props) {
  const [states, setStates] = useState<Record<number, RowState>>({});
  const [anyApproved, setAnyApproved] = useState(false);

  // Reset row states whenever a fresh batch arrives.
  useEffect(() => {
    setStates({});
    setAnyApproved(false);
  }, [suggestions]);

  async function resolve(id: number, action: "approve" | "reject") {
    setStates((s) => ({ ...s, [id]: "busy" }));
    try {
      if (action === "approve") {
        await api.reconciliation.approve(id);
        setStates((s) => ({ ...s, [id]: "approved" }));
        setAnyApproved(true);
      } else {
        await api.reconciliation.reject(id);
        setStates((s) => ({ ...s, [id]: "rejected" }));
      }
    } catch {
      setStates((s) => ({ ...s, [id]: "pending" }));
      toast.error("İşlem başarısız oldu");
    }
  }

  function handleOpenChange(next: boolean) {
    if (!next && anyApproved) onResolved?.();
    onOpenChange(next);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            AI Bütçe Kodu Önerileri
          </DialogTitle>
          <DialogDescription>
            Seçilen ödemeler için AI önerileri. Her biri yalnızca onaylarsan
            uygulanır.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-10 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            AI öneriler üretiliyor (firma araştırması sürebilir)…
          </div>
        ) : suggestions.length === 0 ? (
          <div className="py-10 text-center text-muted-foreground">
            Yeterli sinyal bulunamadı; öneri üretilemedi.
          </div>
        ) : (
          <div className="space-y-3">
            {suggestions.map((s) => {
              const st = states[s.id] ?? "pending";
              const pct = confidencePct(s.score);
              const isWeb = s.reason === "ai_web";
              return (
                <div
                  key={s.id}
                  className="rounded-lg border p-3 flex flex-col gap-2"
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="outline" className="font-mono">
                      {s.proposed_value}
                    </Badge>
                    <span className="text-sm font-medium truncate">
                      {s.candidate_label ?? "(bütçe kalemi eşleşmedi)"}
                    </span>
                    <span className={`text-xs font-semibold ${confidenceColor(pct)}`}>
                      %{pct} güven
                    </span>
                    {isWeb && (
                      <Badge variant="secondary" className="text-[10px] gap-1">
                        <Globe className="h-3 w-3" /> web
                      </Badge>
                    )}
                    <span className="text-[10px] text-muted-foreground ml-auto">
                      ödeme #{s.ledger_entry_id}
                    </span>
                  </div>

                  {s.rationale && (
                    <p className="text-xs text-muted-foreground">{s.rationale}</p>
                  )}

                  <div className="flex items-center gap-2">
                    {st === "approved" ? (
                      <span className="text-xs text-emerald-600 flex items-center gap-1">
                        <Check className="h-3.5 w-3.5" /> Onaylandı, uygulandı
                      </span>
                    ) : st === "rejected" ? (
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <X className="h-3.5 w-3.5" /> Reddedildi
                      </span>
                    ) : (
                      <>
                        <Button
                          size="sm"
                          disabled={st === "busy"}
                          onClick={() => resolve(s.id, "approve")}
                        >
                          {st === "busy" ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Check className="h-3.5 w-3.5 mr-1" />
                          )}
                          Onayla
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={st === "busy"}
                          onClick={() => resolve(s.id, "reject")}
                        >
                          <X className="h-3.5 w-3.5 mr-1" />
                          Reddet
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
