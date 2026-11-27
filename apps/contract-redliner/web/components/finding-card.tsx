"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { api } from "@/lib/api";
import type { FindingOut } from "@/lib/types";
import { EASE } from "@/components/motion";
import { SeverityBadge } from "@/components/ui";

const STATUS_STYLES: Record<string, string> = {
  open: "text-ink-500",
  accepted: "text-emerald-700",
  rejected: "text-red-700",
  dismissed: "text-ink-400 line-through",
};

const ACCENTS: Record<string, string> = {
  critical: "bg-rose-500",
  high: "bg-orange-500",
  medium: "bg-amber-400",
  low: "bg-sky-500",
  info: "bg-slate-400",
};

export function FindingCard(props: { finding: FindingOut; onChanged?: () => void }) {
  const { finding } = props;
  const reduce = useReducedMotion();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(finding.reviewer_note);
  const [expanded, setExpanded] = useState(false);

  async function update(patch: { status?: FindingOut["status"]; reviewer_note?: string }) {
    setBusy(true);
    try {
      await api.patchFinding(finding.id, patch);
      props.onChanged?.();
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.article
      layout
      initial={reduce ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3, ease: EASE }}
      className="group relative overflow-hidden rounded-2xl border border-ink-200/80 bg-white shadow-card transition hover:border-ink-300/80 hover:shadow-lg"
    >
      <span className={["absolute inset-y-0 left-0 w-1", ACCENTS[finding.severity] || "bg-slate-300"].join(" ")} />
      <div className="p-4 pl-5 sm:p-5 sm:pl-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={finding.severity} />
              <h3 className="text-sm font-semibold text-ink-950">{finding.title}</h3>
              <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[10px] font-semibold text-ink-600">
                p. {finding.page}
              </span>
              <span className={["text-[10px] font-semibold uppercase tracking-wide", STATUS_STYLES[finding.status]].join(" ")}>
                {finding.status}
              </span>
            </div>
            <p className="mt-2.5 border-l-2 border-ink-200 pl-3 text-sm italic leading-relaxed text-ink-600">
              “{finding.quote}”
            </p>
          </div>

          <div className="flex shrink-0 gap-1.5">
            <motion.button
              type="button"
              disabled={busy}
              onClick={() => void update({ status: "accepted" })}
              whileTap={reduce ? undefined : { scale: 0.95 }}
              className="rounded-lg bg-emerald-600 px-2.5 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-50"
            >
              Accept
            </motion.button>
            <motion.button
              type="button"
              disabled={busy}
              onClick={() => void update({ status: "rejected" })}
              whileTap={reduce ? undefined : { scale: 0.95 }}
              className="rounded-lg border border-ink-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-ink-700 transition hover:bg-ink-50 disabled:opacity-50"
            >
              Reject
            </motion.button>
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="rounded-lg px-2 py-1.5 text-xs font-medium text-ink-500 transition hover:bg-ink-50"
            >
              {expanded ? "Hide" : "Details"}
            </button>
          </div>
        </div>

        {finding.suggested_text && (
          <div className="mt-3 rounded-xl border border-emerald-100 bg-emerald-50/60 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-800">Proposed redline</p>
            <p className="mt-1 text-sm leading-relaxed text-emerald-950">{finding.suggested_text}</p>
          </div>
        )}

        <AnimatePresence initial={false}>
          {expanded && (
            <motion.div
              initial={reduce ? false : { opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.28, ease: EASE }}
              className="overflow-hidden"
            >
              <div className="mt-3 space-y-3 border-t border-ink-100 pt-3 text-sm">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">Rationale</p>
                  <p className="mt-0.5 text-ink-700">{finding.rationale || "—"}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">Market standard</p>
                  <p className="mt-0.5 text-ink-700">{finding.market_standard || "—"}</p>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-xs text-ink-500">
                  <span>
                    Rule <code className="rounded bg-ink-100 px-1 py-0.5">{finding.rule_id}</code>
                  </span>
                  <span>Confidence {(finding.confidence * 100).toFixed(0)}%</span>
                </div>
                <div>
                  <label
                    className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400"
                    htmlFor={`note-${finding.id}`}
                  >
                    Reviewer note
                  </label>
                  <div className="mt-1 flex gap-2">
                    <input
                      id={`note-${finding.id}`}
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="Add context for your team…"
                      className="flex-1 rounded-lg border border-ink-200 px-3 py-1.5 text-sm outline-none ring-brand-200 focus:ring-2"
                    />
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void update({ reviewer_note: note })}
                      className="rounded-lg bg-ink-950 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-ink-800 disabled:opacity-50"
                    >
                      Save
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.article>
  );
}