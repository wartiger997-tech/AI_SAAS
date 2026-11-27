"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DocumentOut, PlaybookOut, ReviewOut } from "@/lib/types";
import { UploadPanel } from "@/components/upload-panel";
import { Card, Empty, PageHeader, Spinner, StatusPill } from "@/components/ui";

export default function OverviewPage() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [reviews, setReviews] = useState<ReviewOut[]>([]);
  const [playbooks, setPlaybooks] = useState<PlaybookOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
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
      setError(err instanceof Error ? err.message : "Failed to load workspace");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const completed = reviews.filter((review) => review.status === "completed");
  const findingTotal = reviews.reduce((total, review) => total + review.finding_count, 0);

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Upload a contract, run it against a playbook, and export a reviewable redline."
        actions={
          <Link
            href="/documents"
            className="rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm font-medium text-ink-700 hover:bg-ink-50"
          >
            All documents
          </Link>
        }
      />

      {error && <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Documents" value={documents.length} />
        <Stat label="Completed reviews" value={completed.length} />
        <Stat label="Open findings" value={findingTotal} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <Card className="p-5">
          <h2 className="text-sm font-semibold text-ink-900">New review</h2>
          <p className="mb-4 mt-1 text-xs text-ink-500">
            PDF in, page-cited findings out. Nothing leaves your tenant.
          </p>
          {loading ? (
            <Spinner label="Loading playbooks…" />
          ) : (
            <UploadPanel playbooks={playbooks} onUploaded={() => void load()} compact />
          )}
        </Card>

        <Card className="p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink-900">Recent reviews</h2>
            <Link href="/documents" className="text-xs font-medium text-brand-700 hover:underline">
              View all
            </Link>
          </div>
          {loading ? (
            <Spinner />
          ) : reviews.length === 0 ? (
            <Empty title="No reviews yet" hint="Upload your first contract to get started." />
          ) : (
            <ul className="divide-y divide-ink-100">
              {reviews.slice(0, 6).map((review) => {
                const doc = documents.find((item) => item.id === review.document_id);
                return (
                  <li key={review.id}>
                    <Link
                      href={`/reviews/${review.id}`}
                      className="flex items-center justify-between gap-3 py-3 hover:bg-ink-50/60"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-ink-900">
                          {doc?.filename || "Untitled document"}
                        </p>
                        <p className="text-xs text-ink-500">
                          {review.finding_count} findings · {new Date(review.created_at).toLocaleString()}
                        </p>
                      </div>
                      <StatusPill status={review.status} />
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function Stat(props: { label: string; value: number }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-400">{props.label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-ink-900">{props.value}</p>
    </Card>
  );
}