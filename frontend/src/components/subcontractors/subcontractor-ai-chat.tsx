"use client";

import { useRef, useState } from "react";
import { Bot, FileText, Globe, Loader2, Send, User as UserIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api-client";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  source?: "ai" | "fallback";
  usedDocuments?: string[];
}

interface Props {
  subcontractorId: number;
}

const SUGGESTIONS = [
  "Bu sözleşmede ceza maddeleri var mı?",
  "Ödeme koşulları neler?",
  "Sözleşme tutarı ve işin kapsamı nedir?",
  "Kritik tarihler ve teslim süreleri neler?",
];

export function SubcontractorAiChat({ subcontractorId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: q }];
    setMessages(nextMessages);
    // History = previous turns only (without the new question)
    const history = messages.slice(-6).map((m) => ({ role: m.role, content: m.content }));
    try {
      const res = await api.subcontractors.aiChat(subcontractorId, q, history);
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: res.answer,
          source: res.source,
          usedDocuments: res.used_documents,
        },
      ]);
    } catch (err) {
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content:
            err instanceof Error
              ? `Bir hata oluştu: ${err.message}`
              : "Bir hata oluştu, lütfen tekrar dene.",
          source: "fallback",
        },
      ]);
    } finally {
      setBusy(false);
      setTimeout(() => scrollRef.current?.scrollTo({ top: 999999, behavior: "smooth" }), 50);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Bot className="h-4 w-4 text-indigo-500" />
          AI Asistan — Doküman Soru/Cevap
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Yüklenen sözleşme/doküman içeriklerine dayanarak cevaplar. Dokümanda
          olmayan bilgiyi uydurmaz.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => ask(s)}
                disabled={busy}
                className="text-xs px-3 py-1.5 rounded-full border bg-muted/40 hover:bg-muted transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.length > 0 && (
          <div
            ref={scrollRef}
            className="max-h-[420px] overflow-y-auto space-y-3 pr-1"
          >
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-2 ${m.role === "user" ? "justify-end" : ""}`}>
                {m.role === "assistant" && (
                  <div className="h-7 w-7 rounded-full bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center flex-shrink-0">
                    <Bot className="h-4 w-4 text-indigo-600 dark:text-indigo-300" />
                  </div>
                )}
                <div
                  className={`rounded-2xl px-3.5 py-2.5 text-sm whitespace-pre-wrap max-w-[85%] ${
                    m.role === "user"
                      ? "bg-indigo-600 text-white"
                      : "bg-muted/60"
                  }`}
                >
                  {m.content}
                  {m.role === "assistant" && (m.usedDocuments?.length || m.source) ? (
                    <div className="mt-2 pt-2 border-t border-black/10 dark:border-white/10 flex items-center gap-2 flex-wrap">
                      {m.source === "ai" ? (
                        <span className="text-[10px] inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
                          <Globe className="h-3 w-3" /> Claude API
                        </span>
                      ) : (
                        <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">
                          kural tabanlı yanıt
                        </span>
                      )}
                      {(m.usedDocuments ?? []).slice(0, 4).map((d) => (
                        <span
                          key={d}
                          className="text-[10px] inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-background border text-muted-foreground"
                        >
                          <FileText className="h-2.5 w-2.5" /> {d}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                {m.role === "user" && (
                  <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
                    <UserIcon className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
              </div>
            ))}
            {busy && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                AI dokümanları inceliyor…
              </div>
            )}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Dokümanlar hakkında bir soru sor… (örn. ceza maddeleri, ödeme planı)"
            className="flex-1 rounded-lg border px-3 py-2 text-sm bg-background"
            disabled={busy}
          />
          <Button type="submit" size="sm" disabled={busy || !input.trim()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
