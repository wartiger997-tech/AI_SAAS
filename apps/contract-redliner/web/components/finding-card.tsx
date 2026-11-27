"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { FindingOut } from "@/lib/types";
import { Card, SeverityBadge } from "@/components/ui";

const STATUS_STYLES: Record<string, string> = {
  open: "text-ink-500",
  accepted: "text-emerald-700",
  rejected: "text-red-700",
  dismissed: "text-ink-400 line-through",
};

export function FindingCard(props: { finding: FindingOut; onChanged?: () => void }) {
  const { finding } = props;
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
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={finding.severity} />
            <h3 className="text-sm font-semibold text-ink-900">{finding.title}</h3>
            <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[11px] font-medium text-ink-600">
              p. {finding.page}
            </span>
            <span className={["text-[11px] font-semibold uppercase", STATUS_STYLES[finding.status]].join(" ")}>
              {finding.status}
            </span>
          </div>
          <p className="mt-2 border-l-2 border-ink-200 pl-3 text-sm italic text-ink-600">“{finding.quote}”</p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <button
            type="button"
            disabled={busy}
            onClick={() => void update({ status: "accepted" })}
            className="rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            Accept
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void update({ status: "rejected" })}
            className="rounded-md border border-ink-200 px-2.5 py-1 text-xs font-semibold text-ink-700 hover:bg-ink-50 disabled:opacity-50"
          >
            Reject
          </button>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="rounded-md px-2 py-1 text-xs font-medium text-ink-500 hover:bg-ink-50"
          >
            {expanded ? "Hide" : "Details"}
          </button>
        </div>
      </div>

      {finding.suggested_text && (
        <div className="mt-3 rounded-lg bg-emerald-50/70 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-800">Proposed redline</p>
          <p className="mt-1 text-sm text-emerald-950">{finding.suggested_text}</p>
        </div>
      )}

      {expanded && (
        <div className="mt-3 space-y-3 border-t border-ink-100 pt-3 text-sm">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-400">Rationale</p>
            <p className="mt-0.5 text-ink-700">{finding.rationale || "—"}</p>
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-400">Market standard</p>
            <p className="mt-0.5 text-ink-700">{finding.market_standard || "—"}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-ink-500">
            <span>Rule <code className="rounded bg-ink-100 px-1">{finding.rule_id}</code></span>
            <span>Confidence {(finding.confidence * 100).toFixed(0)}%</span>
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-ink-400" htmlFor={`note-${finding.id}`}>
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
                className="rounded-lg bg-ink-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-ink-800 disabled:opacity-50"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}