"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";
import { Card, Empty, PageHeader, Spinner } from "@/components/ui";

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
    <div>
      <PageHeader
        title="Precedent search"
        description="Hybrid retrieval across your precedent library: keyword precision plus vector recall, fused with RRF."
      />

      <form onSubmit={search} className="mb-5 flex gap-2">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          minLength={2}
          required
          placeholder="e.g. limitation of liability cap for SaaS agreements"
          className="flex-1 rounded-lg border border-ink-200 bg-white px-3 py-2.5 text-sm outline-none ring-brand-200 focus:ring-2"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {busy ? "Searching…" : "Search"}
        </button>
      </form>

      {error && <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {busy && <Spinner label="Searching precedent…" />}

      {result && !busy && (
        <>
          <p className="mb-3 text-xs text-ink-500">
            {result.hits.length} hits · {result.took_ms} ms
          </p>
          {result.hits.length === 0 ? (
            <Empty title="No precedent found" hint="Try broader terms or index precedent chunks for this tenant." />
          ) : (
            <div className="space-y-3">
              {result.hits.map((hit) => (
                <Card key={hit.id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-sm font-semibold text-ink-900">{hit.title}</h3>
                    <span className="shrink-0 rounded bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-700">
                      {hit.score.toFixed(3)}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] font-medium uppercase tracking-wide text-ink-400">{hit.source}</p>
                  <p className="mt-2 line-clamp-4 text-sm text-ink-600">{hit.snippet}</p>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}