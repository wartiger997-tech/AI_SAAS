"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { DocumentOut, PlaybookOut } from "@/lib/types";
import { formatBytes } from "@/components/ui";

export function UploadPanel(props: {
  playbooks: PlaybookOut[];
  onUploaded?: (document: DocumentOut) => void;
  compact?: boolean;
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [document, setDocument] = useState<DocumentOut | null>(null);
  const [playbookId, setPlaybookId] = useState(props.playbooks[0]?.id || "");
  const [role, setRole] = useState("customer");

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    setDocument(null);
    try {
      const uploaded = await api.upload(file);
      setDocument(uploaded);
      props.onUploaded?.(uploaded);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function startReview() {
    if (!document) return;
    setBusy(true);
    setError(null);
    try {
      const review = await api.startReview(document.id, playbookId, role);
      router.push(`/reviews/${review.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start review");
      setBusy(false);
    }
  }

  return (
    <div className={props.compact ? "" : "rounded-xl border border-ink-200 bg-white p-5 shadow-card"}>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const file = event.dataTransfer.files?.[0];
          if (file) void upload(file);
        }}
        onClick={() => inputRef.current?.click()}
        className={[
          "cursor-pointer rounded-xl border-2 border-dashed px-5 text-center transition",
          props.compact ? "py-6" : "py-10",
          dragging ? "border-brand-400 bg-brand-50" : "border-ink-300 bg-ink-50/50 hover:border-brand-300",
        ].join(" ")}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void upload(file);
          }}
        />
        <p className="text-sm font-semibold text-ink-800">
          {busy ? "Working…" : "Drop a contract PDF here, or click to browse"}
        </p>
        <p className="mt-1 text-xs text-ink-500">PDF up to 100 MB · 300 pages · page-cited findings</p>
      </div>

      {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {document && (
        <div className="mt-4 rounded-lg border border-ink-200 p-3">
          <p className="truncate text-sm font-medium text-ink-900">{document.filename}</p>
          <p className="text-xs text-ink-500">
            {formatBytes(document.size_bytes)} · {document.page_count || "—"} pages · {document.status}
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_180px_auto]">
            <select
              value={playbookId}
              onChange={(event) => setPlaybookId(event.target.value)}
              className="rounded-lg border border-ink-200 px-3 py-2 text-sm"
            >
              {props.playbooks.length === 0 && <option value="">No playbooks yet</option>}
              {props.playbooks.map((playbook) => (
                <option key={playbook.id} value={playbook.id}>
                  {playbook.name} v{playbook.version}
                </option>
              ))}
            </select>
            <select
              value={role}
              onChange={(event) => setRole(event.target.value)}
              className="rounded-lg border border-ink-200 px-3 py-2 text-sm"
            >
              {["customer", "vendor", "buyer", "seller", "licensor", "licensee"].map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => void startReview()}
              disabled={busy || !playbookId}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              Run review
            </button>
          </div>
        </div>
      )}
    </div>
  );
}