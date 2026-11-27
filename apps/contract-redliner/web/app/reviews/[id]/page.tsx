"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "@/lib/api";
import { SEVERITY_ORDER, type ReviewDetail, type Severity } from "@/lib/types";
import { FindingCard } from "@/components/finding-card";
import { PageTransition, Reveal } from "@/components/motion";
import {
  Card,
  Empty,
  ProgressBar,
  SeverityBadge,
  Skeleton,
  StatusPill,
  formatBytes,
} from "@/components/ui";

const FORMATS = ["docx", "pdf", "md", "json"] as const;

export default function ReviewPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [review, setReview] = useState<ReviewDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [status, setStatus] = useState<"all" | "open" | "accepted" | "rejected">("all");
  const [exporting, setExporting] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.review(id);
      setReview(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!review || review.status === "completed" || review.status === "failed") return;
    const timer = setInterval(() => void load(), 2000);
    return () => clearInterval(timer);
  }, [review, load]);

  const findings = useMemo(() => {
    if (!review) return [];
    return review.findings.filter(
      (finding) =>
        (severity === "all" || finding.severity === severity) &&
        (status === "all" || finding.status === status),
    );
  }, [review, severity, status]);

  async function exportAs(format: (typeof FORMATS)[number]) {
    setExporting(format);
    try {
      await api.exportUrl(id, format);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
    );
  }

  if (!review) {
    return (
      <Empty
        title="Review not found"
        hint={error || "It may belong to another tenant."}
        action={
          <Link href="/documents" className="text-sm font-medium text-brand-700 hover:underline">
            Back to documents
          </Link>
        }
      />
    );
  }

  const counts = SEVERITY_ORDER.map((level) => ({
    level,
    count: review.findings.filter((finding) => finding.severity === level).length,
  }));
  const done = review.status === "completed";
  const failed = review.status === "failed";

  return (
    <PageTransition>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link href="/documents" className="text-xs font-medium text-ink-400 hover:text-ink-600">
            ← Documents
          </Link>
          <h1 className="mt-1 truncate text-2xl font-semibold tracking-tight text-ink-950 sm:text-3xl">
            {review.document.filename}
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            {review.findings.length} findings · reviewer role{" "}
            <span className="capitalize">{review.reviewer_role}</span> ·{" "}
            {new Date(review.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FORMATS.map((format) => (
            <motion.button
              key={format}
              type="button"
              onClick={() => void exportAs(format)}
              disabled={exporting !== null || !done}
              whileTap={{ scale: 0.96 }}
              className="rounded-lg border border-ink-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-700 transition hover:border-ink-300 hover:bg-ink-50 disabled:opacity-40"
            >
              {exporting === format ? "…" : format}
            </motion.button>
          ))}
        </div>
      </div>

      {error && <p className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

      <div className="grid gap-6 xl:grid-cols-[1fr_300px]">
        <div>
          <Reveal>
            <Card className="mb-4 p-4" hover={false}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <StatusPill status={review.status} />
                  <span className="text-xs text-ink-500">
                    {done
                      ? `Model ${review.model || "stub"}`
                      : failed
                        ? review.error || "Review failed"
                        : `Progress ${review.progress}%`}
                  </span>
                </div>
                <div className="text-xs text-ink-500">
                  {formatBytes(review.document.size_bytes)} · {review.document.page_count} pages
                </div>
              </div>
              {!done && !failed && <ProgressBar value={review.progress} className="mt-3" />}
              {done && (
                <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Every finding is page-cited and exportable as tracked changes.
                </div>
              )}
            </Card>
          </Reveal>

          <div className="mb-3 flex flex-wrap items-center gap-1.5">
            <Filter active={severity === "all"} onClick={() => setSeverity("all")}>
              All severities
            </Filter>
            {counts.map(({ level, count }) => (
              <Filter key={level} active={severity === level} onClick={() => setSeverity(level)}>
                <SeverityBadge severity={level} />
                <span className="ml-1 text-ink-500">{count}</span>
              </Filter>
            ))}
            <span className="mx-1 h-4 w-px bg-ink-200" />
            {(["all", "open", "accepted", "rejected"] as const).map((value) => (
              <Filter key={value} active={status === value} onClick={() => setStatus(value)}>
                {value === "all" ? "Any status" : value}
              </Filter>
            ))}
          </div>

          {failed ? (
            <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{review.error}</p>
          ) : findings.length === 0 ? (
            <Empty
              title={review.findings.length === 0 ? "No findings" : "No findings match these filters"}
              hint={
                done
                  ? "This contract appears aligned with the active playbook."
                  : "Findings will appear when the review finishes."
              }
            />
          ) : (
            <motion.div layout className="space-y-3">
              <AnimatePresence initial={false}>
                {findings.map((finding) => (
                  <FindingCard key={finding.id} finding={finding} onChanged={() => void load()} />
                ))}
              </AnimatePresence>
            </motion.div>
          )}
        </div>

        <aside className="hidden xl:block">
          <div className="sticky top-6 space-y-3">
            <Card className="p-4" hover={false}>
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">
                Severity mix
              </p>
              <div className="mt-3 space-y-2">
                {counts.map(({ level, count }) => {
                  const total = Math.max(review.findings.length, 1);
                  return (
                    <div key={level}>
                      <div className="mb-1 flex items-center justify-between text-[11px]">
                        <SeverityBadge severity={level} />
                        <span className="font-medium text-ink-500">{count}</span>
                      </div>
                      <div className="h-1 overflow-hidden rounded-full bg-ink-100">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${(count / total) * 100}%` }}
                          transition={{ duration: 0.6 }}
                          className="h-full rounded-full bg-ink-900/70"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            <Card className="p-4" hover={false}>
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">
                Review facts
              </p>
              <dl className="mt-3 space-y-2 text-xs">
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-400">Playbook</dt>
                  <dd className="truncate font-medium text-ink-700">{review.playbook_id.slice(0, 8)}…</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-400">Clauses</dt>
                  <dd className="font-medium text-ink-700">{review.document.page_count} pages</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-400">Model</dt>
                  <dd className="truncate font-medium text-ink-700">{review.model || "stub"}</dd>
                </div>
              </dl>
              <p className="mt-3 border-t border-ink-100 pt-3 text-[11px] leading-relaxed text-ink-400">
                Exports include the reviewer role, page citations, and a summary table.
              </p>
            </Card>
          </div>
        </aside>
      </div>
    </PageTransition>
  );
}

function Filter(props: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className={[
        "inline-flex items-center rounded-lg border px-2.5 py-1.5 text-xs font-medium transition",
        props.active
          ? "border-brand-200 bg-brand-50 text-brand-800"
          : "border-ink-200 bg-white text-ink-600 hover:bg-ink-50",
      ].join(" ")}
    >
      {props.children}
    </button>
  );
}