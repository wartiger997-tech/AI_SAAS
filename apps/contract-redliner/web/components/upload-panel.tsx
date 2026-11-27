"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { api } from "@/lib/api";
import type { DocumentOut, PlaybookOut } from "@/lib/types";
import { EASE } from "@/components/motion";
import { formatBytes } from "@/components/ui";

export function UploadPanel(props: {
  playbooks: PlaybookOut[];
  onUploaded?: (document: DocumentOut) => void;
  compact?: boolean;
}) {
  const router = useRouter();
  const reduce = useReducedMotion();
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
    <div className={props.compact ? "" : "rounded-2xl border border-ink-200/80 bg-white p-5 shadow-card"}>
      <motion.div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
        }}
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
        animate={
          reduce
            ? undefined
            : {
                scale: dragging ? 1.015 : 1,
                borderColor: dragging ? "rgba(51,99,255,.55)" : "rgba(213,217,226,1)",
                backgroundColor: dragging ? "rgba(238,244,255,.7)" : "rgba(246,247,249,.5)",
              }
        }
        transition={{ duration: 0.2 }}
        className={[
          "group relative cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed px-5 text-center outline-none ring-brand-200 focus-visible:ring-2",
          props.compact ? "py-6" : "py-10",
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
        <motion.div
          animate={reduce ? undefined : { y: dragging ? -4 : 0 }}
          className="mx-auto grid h-11 w-11 place-items-center rounded-xl border border-ink-200 bg-white text-ink-500 shadow-sm transition group-hover:text-brand-600"
        >
          <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
            <path d="M12 16V4m0 0L8 8m4-4 4 4M5 16v3h14v-3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </motion.div>
        <p className="mt-3 text-sm font-semibold text-ink-800">
          {busy ? "Uploading and extracting…" : "Drop a contract PDF here, or click to browse"}
        </p>
        <p className="mt-1 text-xs text-ink-500">PDF up to 100 MB · 300 pages · page-cited findings</p>
        {busy && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mx-auto mt-4 h-1 w-40 overflow-hidden rounded-full bg-ink-200"
          >
            <motion.div
              animate={reduce ? undefined : { x: ["-100%", "100%"] }}
              transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
              className="h-full w-1/2 rounded-full bg-brand-500"
            />
          </motion.div>
        )}
      </motion.div>

      {error && (
        <motion.p
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {error}
        </motion.p>
      )}

      <AnimatePresence>
        {document && (
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 10, height: 0 }}
            animate={{ opacity: 1, y: 0, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: EASE }}
            className="overflow-hidden"
          >
            <div className="mt-4 rounded-xl border border-ink-200 bg-ink-50/50 p-3">
              <div className="flex items-center gap-2">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-white text-[10px] font-bold text-rose-600 shadow-sm">
                  PDF
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink-900">{document.filename}</p>
                  <p className="text-xs text-ink-500">
                    {formatBytes(document.size_bytes)} · {document.page_count || "—"} pages · {document.status}
                  </p>
                </div>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_170px_auto]">
                <select
                  value={playbookId}
                  onChange={(event) => setPlaybookId(event.target.value)}
                  className="rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm outline-none ring-brand-200 focus:ring-2"
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
                  className="rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm outline-none ring-brand-200 focus:ring-2"
                >
                  {["customer", "vendor", "buyer", "seller", "licensor", "licensee"].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
                <motion.button
                  type="button"
                  onClick={() => void startReview()}
                  disabled={busy || !playbookId}
                  whileTap={reduce ? undefined : { scale: 0.97 }}
                  className="rounded-lg bg-ink-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink-800 disabled:opacity-50"
                >
                  Run review
                </motion.button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}