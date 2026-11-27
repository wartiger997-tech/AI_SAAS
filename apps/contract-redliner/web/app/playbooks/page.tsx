"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "@/lib/api";
import type { PlaybookOut } from "@/lib/types";
import { PageTransition, Stagger, StaggerItem } from "@/components/motion";
import { Card, Empty, PageHeader, Skeleton } from "@/components/ui";

const SAMPLE_RULES = JSON.stringify(
  [
    {
      id: "liability_cap_low",
      title: "Liability cap below market",
      category: "liability",
      severity: "high",
      description: "Vendor liability is capped below twelve months of fees.",
      patterns: ["liab", "cap on liability"],
      must_include: ["12", "twelve"],
      market_standard: "12 months' fees",
      guidance: "Negotiate a 12-month fee cap with carve-outs.",
      suggested_text: "Twelve (12) months of fees paid or payable.",
      redline_strategy: "replace",
    },
    {
      id: "auto_renew",
      title: "Auto-renewal without notice",
      category: "termination",
      severity: "medium",
      patterns: ["automatically renew", "auto-renew"],
      must_include: ["30", "thirty"],
      market_standard: "30 days' written notice",
      guidance: "Require 30 days' notice before renewal.",
      suggested_text: "Either party may prevent renewal with thirty (30) days' notice.",
      redline_strategy: "insert_after",
    },
  ],
  null,
  2,
);

export default function PlaybooksPage() {
  const [playbooks, setPlaybooks] = useState<PlaybookOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [rules, setRules] = useState(SAMPLE_RULES);

  const load = useCallback(async () => {
    try {
      setPlaybooks(await api.playbooks());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load playbooks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const parsedCount = useMemo(() => {
    try {
      const parsed = JSON.parse(rules);
      return Array.isArray(parsed) ? parsed.length : 0;
    } catch {
      return 0;
    }
  }, [rules]);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const parsed = JSON.parse(rules);
      if (!Array.isArray(parsed) || parsed.length === 0) throw new Error("rules must be a non-empty array");
      await api.createPlaybook({ name, description, rules: parsed });
      setName("");
      setDescription("");
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid playbook");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageTransition>
      <PageHeader
        eyebrow="Rule library"
        title="Playbooks"
        description="Versioned rule sets. Every review runs against an active playbook, and every version is immutable."
        actions={
          <motion.button
            type="button"
            onClick={() => setShowForm(!showForm)}
            whileTap={{ scale: 0.97 }}
            className="rounded-xl bg-ink-950 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-ink-950/10 transition hover:bg-ink-800"
          >
            {showForm ? "Close" : "New playbook"}
          </motion.button>
        }
      />

      {error && <p className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

      <AnimatePresence initial={false}>
        {showForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <Card className="mb-5 p-5" hover={false}>
              <form onSubmit={create} className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block">
                    <span className="mb-1 block text-xs font-medium text-ink-600">Name</span>
                    <input
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      required
                      minLength={2}
                      placeholder="Acme SaaS Playbook"
                      className="w-full rounded-xl border border-ink-200 px-3 py-2.5 text-sm outline-none ring-brand-200 focus:ring-2"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-medium text-ink-600">Description</span>
                    <input
                      value={description}
                      onChange={(event) => setDescription(event.target.value)}
                      placeholder="Standard positions for customer paper"
                      className="w-full rounded-xl border border-ink-200 px-3 py-2.5 text-sm outline-none ring-brand-200 focus:ring-2"
                    />
                  </label>
                </div>
                <label className="block">
                  <span className="mb-1 flex items-center justify-between text-xs font-medium text-ink-600">
                    Rules (JSON array)
                    <span className="text-[10px] font-normal text-ink-400">{parsedCount} parsed</span>
                  </span>
                  <textarea
                    value={rules}
                    onChange={(event) => setRules(event.target.value)}
                    rows={14}
                    spellCheck={false}
                    className="w-full rounded-xl border border-ink-200 bg-ink-50/60 px-3 py-2 font-mono text-xs outline-none ring-brand-200 focus:ring-2"
                  />
                </label>
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-xl bg-ink-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-800 disabled:opacity-50"
                >
                  {busy ? "Saving…" : "Create playbook"}
                </button>
              </form>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-36" />
          <Skeleton className="h-36" />
        </div>
      ) : playbooks.length === 0 ? (
        <Empty
          title="No playbooks"
          hint="Create one, or register a workspace to get the seeded NDA and SaaS playbooks."
        />
      ) : (
        <Stagger className="grid gap-4 md:grid-cols-2">
          {playbooks.map((playbook) => (
            <StaggerItem key={playbook.id}>
              <Card className="group h-full p-5" hover>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600">
                      <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
                        <path d="M4 5h16v14H4zM8 9h8M8 13h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                      </svg>
                    </span>
                    <div>
                      <h3 className="text-sm font-semibold text-ink-950">{playbook.name}</h3>
                      <p className="mt-0.5 line-clamp-1 text-xs text-ink-500">
                        {playbook.description || "No description"}
                      </p>
                    </div>
                  </div>
                  <span className="rounded-lg bg-ink-100 px-2 py-0.5 text-xs font-semibold text-ink-600">
                    v{playbook.version}
                  </span>
                </div>
                <div className="mt-4 flex items-center justify-between border-t border-ink-100 pt-3 text-xs">
                  <span className="text-ink-500">{playbook.rule_count} rules</span>
                  <span
                    className={
                      playbook.is_active
                        ? "inline-flex items-center gap-1 font-semibold text-emerald-700"
                        : "text-ink-400"
                    }
                  >
                    {playbook.is_active && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />}
                    {playbook.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
              </Card>
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </PageTransition>
  );
}