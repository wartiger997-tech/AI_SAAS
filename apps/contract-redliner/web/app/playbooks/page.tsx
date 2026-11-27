"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PlaybookOut } from "@/lib/types";
import { Card, Empty, PageHeader, Spinner } from "@/components/ui";

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
    <div>
      <PageHeader
        title="Playbooks"
        description="Versioned rule sets. A new upload always runs against an active playbook."
        actions={
          <button
            type="button"
            onClick={() => setShowForm(!showForm)}
            className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          >
            {showForm ? "Close" : "New playbook"}
          </button>
        }
      />

      {error && <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {showForm && (
        <Card className="mb-5 p-5">
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
                  className="w-full rounded-lg border border-ink-200 px-3 py-2 text-sm outline-none ring-brand-200 focus:ring-2"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-ink-600">Description</span>
                <input
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Standard positions for customer paper"
                  className="w-full rounded-lg border border-ink-200 px-3 py-2 text-sm outline-none ring-brand-200 focus:ring-2"
                />
              </label>
            </div>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-600">Rules (JSON array)</span>
              <textarea
                value={rules}
                onChange={(event) => setRules(event.target.value)}
                rows={14}
                spellCheck={false}
                className="w-full rounded-lg border border-ink-200 bg-ink-50/50 px-3 py-2 font-mono text-xs outline-none ring-brand-200 focus:ring-2"
              />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-ink-900 px-4 py-2 text-sm font-semibold text-white hover:bg-ink-800 disabled:opacity-50"
            >
              {busy ? "Saving…" : "Create playbook"}
            </button>
          </form>
        </Card>
      )}

      {loading ? (
        <Spinner />
      ) : playbooks.length === 0 ? (
        <Empty title="No playbooks" hint="Create one, or register a workspace to get the seeded NDA and SaaS playbooks." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {playbooks.map((playbook) => (
            <Card key={playbook.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-ink-900">{playbook.name}</h3>
                  <p className="mt-1 text-xs text-ink-500">{playbook.description || "No description"}</p>
                </div>
                <span className="rounded bg-ink-100 px-2 py-0.5 text-xs font-semibold text-ink-600">
                  v{playbook.version}
                </span>
              </div>
              <div className="mt-4 flex items-center justify-between text-xs text-ink-500">
                <span>{playbook.rule_count} rules</span>
                <span className={playbook.is_active ? "font-semibold text-emerald-700" : "text-ink-400"}>
                  {playbook.is_active ? "Active" : "Inactive"}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}