"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import type { DocumentOut, PlaybookOut, ReviewOut } from "@/lib/types";
import { Hero } from "@/components/hero";
import { UploadPanel } from "@/components/upload-panel";
import { PageTransition, Reveal, Stagger, StaggerItem } from "@/components/motion";
import { Card, Empty, Skeleton, StatCard, StatusPill } from "@/components/ui";

export default function OverviewPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [reviews, setReviews] = useState<ReviewOut[]>([]);
  const [playbooks, setPlaybooks] = useState<PlaybookOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [docs, revs, books] = await Promise.all([api.documents(), api.reviews(), api.playbooks()]);
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
    <PageTransition>
      <Hero
        onPrimary={() => document.getElementById("new-review")?.scrollIntoView({ behavior: "smooth", block: "center" })}
        onSecondary={() => router.push("/playbooks")}
      />

      {error && <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {loading ? (
          <>
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </>
        ) : (
          <>
            <StatCard label="Documents" value={documents.length} hint="PDFs in your tenant" />
            <StatCard label="Completed reviews" value={completed.length} hint="Ready to export" accent="emerald" />
            <StatCard label="Open findings" value={findingTotal} hint="Across all reviews" accent="amber" />
          </>
        )}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.05fr_1fr]" id="new-review">
        <Reveal>
          <Card className="p-5" hover={false}>
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-ink-950">New review</h2>
                <p className="mt-0.5 text-xs text-ink-500">PDF in, page-cited findings out.</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                SOC-ready
              </span>
            </div>
            {loading ? <Skeleton className="h-44" /> : <UploadPanel playbooks={playbooks} onUploaded={() => void load()} compact />}
          </Card>
        </Reveal>

        <Reveal delay={0.08}>
          <Card className="p-5" hover={false}>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink-950">Recent reviews</h2>
              <Link href="/documents" className="text-xs font-medium text-brand-700 hover:underline">
                View all
              </Link>
            </div>
            {loading ? (
              <div className="space-y-2 pt-2">
                <Skeleton className="h-14" />
                <Skeleton className="h-14" />
                <Skeleton className="h-14" />
              </div>
            ) : reviews.length === 0 ? (
              <Empty title="No reviews yet" hint="Upload your first contract to get started." />
            ) : (
              <Stagger className="divide-y divide-ink-100">
                {reviews.slice(0, 6).map((review) => {
                  const doc = documents.find((item) => item.id === review.document_id);
                  return (
                    <StaggerItem key={review.id}>
                      <Link
                        href={`/reviews/${review.id}`}
                        className="group flex items-center justify-between gap-3 py-3 transition hover:bg-ink-50/60"
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-rose-50 text-[9px] font-bold uppercase text-rose-600">
                            PDF
                          </span>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-ink-900 group-hover:text-brand-700">
                              {doc?.filename || "Untitled document"}
                            </p>
                            <p className="text-xs text-ink-500">
                              {review.finding_count} findings · {new Date(review.created_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <StatusPill status={review.status} />
                      </Link>
                    </StaggerItem>
                  );
                })}
              </Stagger>
            )}
          </Card>
        </Reveal>
      </div>

      <Reveal delay={0.1}>
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {[
            {
              step: "01",
              title: "Extract",
              body: "Page-aware text and tables, with block geometry preserved for citations.",
            },
            {
              step: "02",
              title: "Evaluate",
              body: "Deterministic rules plus LLM reasoning against your versioned playbook.",
            },
            {
              step: "03",
              title: "Export",
              body: "Tracked-changes DOCX, annotated PDF, Markdown, or JSON — reviewer ready.",
            },
          ].map((item, index) => (
            <motion.div
              key={item.step}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.45, delay: index * 0.08 }}
              className="relative rounded-2xl border border-ink-200/70 bg-white/60 p-4"
            >
              <span className="font-mono text-[10px] font-semibold text-brand-600">{item.step}</span>
              <p className="mt-1 text-sm font-semibold text-ink-900">{item.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-ink-500">{item.body}</p>
            </motion.div>
          ))}
        </div>
      </Reveal>

      <p className="mt-8 text-center text-[11px] text-ink-400">
        ClauseGuard is not legal advice. Every redline is a starting point for counsel review.
      </p>
    </PageTransition>
  );
}