"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { SEVERITY_ORDER, type ReviewDetail, type Severity } from "@/lib/types";
import { FindingCard } from "@/components/finding-card";
import { Card, Empty, PageHeader, SeverityBadge, Spinner, StatusPill, formatBytes } from "@/components/ui";

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

  async function exportAs(format: "docx" | "pdf" | "md" | "json") {
    setExporting(format);
    try {
      await api.exportUrl(id, format);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(null);
    }
  }

  if (loading) return <Spinner label="Loading review…" />;

  if (!review) {
    return (
      <Empty
        title="Review not found"
        hint={error || "It may belong to another tenant."}
        action={<Link href="/documents" className="text-sm font-medium text-brand-700 hover:underline">Back to documents</Link>}
      />
    );
  }

  const counts = SEVERITY_ORDER.map((level) => ({
    level,
    count: review.findings.filter((finding) => finding.severity === level).length,
  }));

  return (
    <div>
      <PageHeader
        title={review.document.filename}
        description={`${review.findings.length} findings · reviewer role ${review.reviewer_role} · ${new Date(review.created_at).toLocaleString()}`}
        actions={
          <div className="flex flex-wrap gap-2">
            {(["docx", "pdf", "md", "json"] as const).map((format) => (
              <button
                key={format}
                type="button"
                onClick={() => void exportAs(format)}
                disabled={exporting !== null || review.status !== "completed"}
                className="rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-semibold uppercase text-ink-700 hover:bg-ink-50 disabled:opacity-50"
              >
                {exporting === format ? "…" : format}
              </button>
            ))}
          </div>
        }
      />

      {error && <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <Card className="mb-5 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <StatusPill status={review.status} />
            <span className="text-xs text-ink-500">
              {review.status === "completed"
                ? `Model ${review.model || "stub"}`
                : review.error || `Progress ${review.progress}%`}
            </span>
          </div>
          <div className="text-xs text-ink-500">
            {formatBytes(review.document.size_bytes)} · {review.document.page_count} pages
          </div>
        </div>
        {review.status !== "completed" && review.status !== "failed" && (
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink-100">
            <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${review.progress}%` }} />
          </div>
        )}
      </Card>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <FilterButton active={severity === "all"} onClick={() => setSeverity("all")}>All severities</FilterButton>
        {counts.map(({ level, count }) => (
          <FilterButton key={level} active={severity === level} onClick={() => setSeverity(level)}>
            <SeverityBadge severity={level} /> <span className="ml-1 text-ink-500">{count}</span>
          </FilterButton>
        ))}
        <span className="mx-2 h-4 w-px bg-ink-200" />
        {(["all", "open", "accepted", "rejected"] as const).map((value) => (
          <FilterButton key={value} active={status === value} onClick={() => setStatus(value)}>
            {value === "all" ? "Any status" : value}
          </FilterButton>
        ))}
      </div>

      {review.status === "failed" ? (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{review.error}</p>
      ) : findings.length === 0 ? (
        <Empty
          title={review.findings.length === 0 ? "No findings" : "No findings match these filters"}
          hint={review.status === "completed" ? "This contract appears aligned with the active playbook." : "Findings will appear when the review finishes."}
        />
      ) : (
        <div className="space-y-3">
          {findings.map((finding) => (
            <FindingCard key={finding.id} finding={finding} onChanged={() => void load()} />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterButton(props: {
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