import type { ReactNode } from "react";
import { SEVERITY_STYLES, type Severity } from "@/lib/types";

export function PageHeader(props: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{props.title}</h1>
        {props.description && <p className="mt-1 text-sm text-ink-500">{props.description}</p>}
      </div>
      {props.actions}
    </div>
  );
}

export function Card(props: { children: ReactNode; className?: string }) {
  return (
    <div className={["rounded-xl border border-ink-200 bg-white shadow-card", props.className || ""].join(" ")}>
      {props.children}
    </div>
  );
}

export function SeverityBadge(props: { severity: Severity }) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset",
        SEVERITY_STYLES[props.severity],
      ].join(" ")}
    >
      {props.severity}
    </span>
  );
}

export function StatusPill(props: { status: string }) {
  const tone =
    props.status === "completed"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
      : props.status === "failed"
        ? "bg-red-50 text-red-700 ring-red-200"
        : "bg-sky-50 text-sky-700 ring-sky-200";
  return (
    <span className={["inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset", tone].join(" ")}>
      {props.status}
    </span>
  );
}

export function Empty(props: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-ink-300 bg-white/60 px-6 py-12 text-center">
      <p className="text-sm font-medium text-ink-700">{props.title}</p>
      {props.hint && <p className="mt-1 text-sm text-ink-500">{props.hint}</p>}
      {props.action && <div className="mt-4 flex justify-center">{props.action}</div>}
    </div>
  );
}

export function Spinner(props: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-200 border-t-brand-600" />
      {props.label || "Loading…"}
    </div>
  );
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}