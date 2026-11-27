"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DocumentOut, PlaybookOut, ReviewOut } from "@/lib/types";
import { UploadPanel } from "@/components/upload-panel";
import { Card, Empty, PageHeader, Spinner, StatusPill, formatBytes } from "@/components/ui";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [reviews, setReviews] = useState<ReviewOut[]>([]);
  const [playbooks, setPlaybooks] = useState<PlaybookOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [docs, revs, books] = await Promise.all([
        api.documents(),
        api.reviews(),
        api.playbooks(),
      ]);
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

  return (
    <div>
      <PageHeader
        title="Documents"
        description="Every upload is stored per tenant and processed asynchronously."
      />
      {error && <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <Card className="h-fit p-5">
          <h2 className="mb-3 text-sm font-semibold text-ink-900">Upload contract</h2>
          {loading ? <Spinner label="Loading playbooks…" /> : <UploadPanel playbooks={playbooks} onUploaded={() => void load()} />}
        </Card>

        <div>
          {loading ? (
            <Spinner />
          ) : documents.length === 0 ? (
            <Empty title="No documents yet" hint="Upload a PDF to run your first review." />
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => {
                const review = reviews.find((item) => item.document_id === doc.id);
                return (
                  <Card key={doc.id} className="flex items-center justify-between gap-3 p-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink-900">{doc.filename}</p>
                      <p className="mt-0.5 text-xs text-ink-500">
                        {formatBytes(doc.size_bytes)} · {doc.page_count || "—"} pages · {doc.status}
                        {doc.error ? ` · ${doc.error}` : ""}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {review ? (
                        <>
                          <StatusPill status={review.status} />
                          <Link
                            href={`/reviews/${review.id}`}
                            className="rounded-lg bg-ink-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-ink-800"
                          >
                            Open
                          </Link>
                        </>
                      ) : (
                        <span className="text-xs text-ink-400">No review</span>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}