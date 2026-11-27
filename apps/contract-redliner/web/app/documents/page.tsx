"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "@/lib/api";
import type { DocumentOut, PlaybookOut, ReviewOut } from "@/lib/types";
import { UploadPanel } from "@/components/upload-panel";
import { PageTransition, Reveal, Stagger, StaggerItem } from "@/components/motion";
import {
  Card,
  Empty,
  PageHeader,
  Skeleton,
  StatusPill,
  formatBytes,
} from "@/components/ui";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [reviews, setReviews] = useState<ReviewOut[]>([]);
  const [playbooks, setPlaybooks] = useState<PlaybookOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      const [docs, revs, books] = await Promise.all([api.documents(), api.reviews(), api.playbooks()]);
      setDocuments(docs);
      setReviews(revs);
      setPlaybooks(books);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return documents;
    return documents.filter((doc) => doc.filename.toLowerCase().includes(needle));
  }, [documents, query]);

  return (
    <PageTransition>
      <PageHeader
        eyebrow="Library"
        title="Documents"
        description="Every upload is stored per tenant and processed asynchronously with page-level citations."
        actions={
          <div className="flex items-center gap-2">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter by filename…"
              className="w-44 rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm outline-none ring-brand-200 focus:ring-2 sm:w-56"
            />
            <span className="rounded-lg bg-ink-100 px-2.5 py-1.5 text-xs font-semibold text-ink-600">
              {filtered.length}
            </span>
          </div>
        }
      />

      {error && <p className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.45fr]">
        <Reveal>
          <Card className="h-fit p-5" hover={false}>
            <h2 className="mb-3 text-sm font-semibold text-ink-950">Upload contract</h2>
            {loading ? (
              <Skeleton className="h-48" />
            ) : (
              <UploadPanel playbooks={playbooks} onUploaded={() => void load()} />
            )}
          </Card>
        </Reveal>

        <div>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
            </div>
          ) : filtered.length === 0 ? (
            <Empty
              title={documents.length === 0 ? "No documents yet" : "No documents match your filter"}
              hint={documents.length === 0 ? "Upload a PDF to run your first review." : "Try a different filename."}
            />
          ) : (
            <Stagger className="space-y-2">
              <AnimatePresence initial={false}>
                {filtered.map((doc) => {
                  const review = reviews.find((item) => item.document_id === doc.id);
                  return (
                    <StaggerItem key={doc.id}>
                      <motion.div layout exit={{ opacity: 0, y: -6 }}>
                        <Card className="group flex items-center justify-between gap-3 p-4" hover>
                          <div className="flex min-w-0 items-center gap-3">
                            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-rose-50 text-[9px] font-bold uppercase text-rose-600">
                              PDF
                            </span>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-ink-950">{doc.filename}</p>
                              <p className="mt-0.5 truncate text-xs text-ink-500">
                                {formatBytes(doc.size_bytes)} · {doc.page_count || "—"} pages · {doc.status}
                                {doc.error ? ` · ${doc.error}` : ""}
                              </p>
                            </div>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {review ? (
                              <>
                                <StatusPill status={review.status} />
                                <Link
                                  href={`/reviews/${review.id}`}
                                  className="rounded-lg bg-ink-950 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-ink-800"
                                >
                                  Open
                                </Link>
                              </>
                            ) : (
                              <span className="text-xs text-ink-400">No review</span>
                            )}
                          </div>
                        </Card>
                      </motion.div>
                    </StaggerItem>
                  );
                })}
              </AnimatePresence>
            </Stagger>
          )}
        </div>
      </div>
    </PageTransition>
  );
}