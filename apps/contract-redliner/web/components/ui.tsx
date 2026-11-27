"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { AnimatedNumber, EASE } from "@/components/motion";
import { SEVERITY_STYLES, type Severity } from "@/lib/types";

export function PageHeader(props: {
  title: string;
  description?: string;
  actions?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        {props.eyebrow && (
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-600">
            {props.eyebrow}
          </p>
        )}
        <motion.h1
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: EASE }}
          className="text-2xl font-semibold tracking-tight text-ink-950 sm:text-3xl"
        >
          {props.title}
        </motion.h1>
        {props.description && <p className="mt-1 max-w-2xl text-sm text-ink-500">{props.description}</p>}
      </div>
      {props.actions}
    </div>
  );
}

export function Card(props: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}) {
  return (
    <motion.div
      whileHover={props.hover ? { y: -3, boxShadow: "0 18px 40px -18px rgba(16,24,40,.22)" } : undefined}
      transition={{ duration: 0.25, ease: EASE }}
      className={["rounded-2xl border border-ink-200/80 bg-white shadow-card", props.className || ""].join(" ")}
    >
      {props.children}
    </motion.div>
  );
}

export function SeverityBadge(props: { severity: Severity }) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset",
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
        : props.status === "queued"
          ? "bg-amber-50 text-amber-700 ring-amber-200"
          : "bg-sky-50 text-sky-700 ring-sky-200";
  return (
    <span
      className={[
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset",
        tone,
      ].join(" ")}
    >
      {props.status === "completed" && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />}
      {props.status}
    </span>
  );
}

export function Empty(props: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EASE }}
      className="rounded-2xl border border-dashed border-ink-300 bg-white/60 px-6 py-12 text-center"
    >
      <div className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-ink-100 text-ink-400">
        <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
          <path d="M7 3h7l4 4v14H7zM14 3v5h5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="mt-3 text-sm font-medium text-ink-700">{props.title}</p>
      {props.hint && <p className="mt-1 text-sm text-ink-500">{props.hint}</p>}
      {props.action && <div className="mt-4 flex justify-center">{props.action}</div>}
    </motion.div>
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

export function Skeleton(props: { className?: string }) {
  return <div className={["animate-pulse rounded-lg bg-ink-100", props.className || ""].join(" ")} />;
}

export function ProgressBar(props: { value: number; className?: string }) {
  return (
    <div className={["h-1.5 overflow-hidden rounded-full bg-ink-100", props.className || ""].join(" ")}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(100, Math.max(0, props.value))}%` }}
        transition={{ duration: 0.6, ease: EASE }}
        className="h-full rounded-full bg-gradient-to-r from-brand-500 to-indigo-500"
      />
    </div>
  );
}

export function StatCard(props: {
  label: string;
  value: number;
  hint?: string;
  accent?: "brand" | "emerald" | "amber";
  suffix?: string;
}) {
  const accent = {
    brand: "from-brand-500/15 to-indigo-500/5 text-brand-600",
    emerald: "from-emerald-500/15 to-teal-500/5 text-emerald-600",
    amber: "from-amber-500/15 to-orange-500/5 text-amber-600",
  }[props.accent || "brand"];
  return (
    <Card className="relative overflow-hidden p-5" hover>
      <div className={["pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-gradient-to-br blur-2xl", accent].join(" ")} />
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">{props.label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-ink-950">
        <AnimatedNumber value={props.value} suffix={props.suffix} />
      </p>
      {props.hint && <p className="mt-1 text-xs text-ink-400">{props.hint}</p>}
    </Card>
  );
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}