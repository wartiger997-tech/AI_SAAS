"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";
import { PageTransition, Reveal, Stagger, StaggerItem } from "@/components/motion";
import { Card, Empty, PageHeader, Skeleton } from "@/components/ui";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await api.search(query));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageTransition>
      <PageHeader
        eyebrow="Retrieval"
        title="Precedent search"
        description="Hybrid retrieval across your precedent library: keyword precision plus vector recall, fused with Reciprocal Rank Fusion."
      />

      <Reveal>
        <form onSubmit={search} className="relative mb-6">
          <div className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-400">
            <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
              <path d="M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm5 12 4 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </div>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            minLength={2}
            required
            placeholder="e.g. limitation of liability cap for SaaS agreements"
            className="w-full rounded-2xl border border-ink-200 bg-white py-3.5 pl-12 pr-32 text-sm shadow-card outline-none ring-brand-200 transition focus:ring-2"
          />
          <motion.button
            type="submit"
            disabled={busy}
            whileTap={{ scale: 0.97 }}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-xl bg-ink-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-800 disabled:opacity-50"
          >
            {busy ? "Searching…" : "Search"}
          </motion.button>
        </form>
      </Reveal>

      {error && <p className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
      {busy && (
        <div className="space-y-2">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      )}

      <AnimatePresence mode="wait">
        {result && !busy && (
          <motion.div
            key={result.query + result.took_ms}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <p className="mb-3 text-xs text-ink-500">
              {result.hits.length} hits · {result.took_ms} ms · query “{result.query}”
            </p>
            {result.hits.length === 0 ? (
              <Empty
                title="No precedent found"
                hint="Try broader terms or index precedent chunks for this tenant."
              />
            ) : (
              <Stagger className="space-y-3">
                {result.hits.map((hit) => (
                  <StaggerItem key={hit.id}>
                    <Card className="p-4" hover>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="truncate text-sm font-semibold text-ink-950">{hit.title}</h3>
                          <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">
                            {hit.source}
                          </p>
                        </div>
                        <div className="shrink-0 text-right">
                          <span className="rounded-lg bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-700">
                            {hit.score.toFixed(3)}
                          </span>
                          <p className="mt-1 text-[10px] text-ink-400">score</p>
                        </div>
                      </div>
                      <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-ink-600">{hit.snippet}</p>
                    </Card>
                  </StaggerItem>
                ))}
              </Stagger>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </PageTransition>
  );
}