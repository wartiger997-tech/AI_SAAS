"use client";

import dynamic from "next/dynamic";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { api, getToken, setToken } from "@/lib/api";
import type { UserOut } from "@/lib/types";
import { EASE } from "@/components/motion";

const HeroScene = dynamic(() => import("@/components/hero-scene"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse rounded-2xl bg-white/60" />,
});

interface AuthState {
  user: UserOut | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (input: {
    tenant_name: string;
    email: string;
    password: string;
    full_name?: string;
  }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        await api.login(email, password);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Login failed");
        throw err;
      }
    },
    [refresh],
  );

  const register = useCallback(
    async (input: {
      tenant_name: string;
      email: string;
      password: string;
      full_name?: string;
    }) => {
      setError(null);
      try {
        await api.register(input);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Registration failed");
        throw err;
      }
    },
    [refresh],
  );

  const logout = useCallback(() => {
    api.logout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, error, login, register, logout }),
    [user, loading, error, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export function LoginPanel() {
  const { login, register, error } = useAuth();
  const reduce = useReducedMotion();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    const data = new FormData(event.currentTarget);
    try {
      if (mode === "login") {
        await login(String(data.get("email")), String(data.get("password")));
      } else {
        await register({
          tenant_name: String(data.get("tenant_name")),
          email: String(data.get("email")),
          password: String(data.get("password")),
          full_name: String(data.get("full_name") || ""),
        });
      }
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen bg-ink-50 lg:grid-cols-[1.05fr_0.95fr]">
      <div className="flex items-center justify-center px-5 py-10 sm:px-10">
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: EASE }}
          className="w-full max-w-md"
        >
          <div className="mb-8 flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-ink-950 text-sm font-bold text-white shadow-lg">
              CG
            </span>
            <span className="text-sm font-semibold tracking-tight text-ink-900">ClauseGuard</span>
          </div>

          <div className="rounded-2xl border border-ink-200 bg-white p-6 shadow-card sm:p-7">
            <div className="mb-5 inline-flex rounded-xl bg-ink-100 p-1">
              {(["login", "register"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => {
                    setMode(value);
                    setFormError(null);
                  }}
                  className="relative rounded-lg px-3.5 py-1.5 text-xs font-semibold capitalize text-ink-500 transition"
                >
                  {mode === value && (
                    <motion.span
                      layoutId="auth-tab"
                      className="absolute inset-0 rounded-lg bg-white shadow-sm"
                      transition={{ type: "spring", stiffness: 380, damping: 32 }}
                    />
                  )}
                  <span className={mode === value ? "relative text-ink-900" : "relative"}>
                    {value === "login" ? "Sign in" : "Create account"}
                  </span>
                </button>
              ))}
            </div>

            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={mode}
                initial={reduce ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.22, ease: EASE }}
              >
                <h1 className="text-xl font-semibold tracking-tight text-ink-950">
                  {mode === "login" ? "Welcome back" : "Create your workspace"}
                </h1>
                <p className="mt-1 text-sm text-ink-500">
                  {mode === "login"
                    ? "Sign in to review contracts with page-cited findings."
                    : "Start with a seeded NDA and SaaS playbook."}
                </p>

                <form onSubmit={submit} className="mt-5 space-y-3">
                  {mode === "register" && (
                    <>
                      <Field label="Company" name="tenant_name" placeholder="Acme Legal" required />
                      <Field label="Full name" name="full_name" placeholder="Ada Lovelace" />
                    </>
                  )}
                  <Field
                    label="Work email"
                    name="email"
                    type="email"
                    placeholder="you@company.com"
                    required
                    autoComplete="email"
                  />
                  <div className="relative">
                    <Field
                      label="Password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      placeholder="At least 10 characters"
                      required
                      minLength={10}
                      autoComplete={mode === "login" ? "current-password" : "new-password"}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2 top-[26px] rounded px-2 py-1 text-[11px] font-medium text-ink-400 hover:text-ink-600"
                    >
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>

                  {(formError || error) && (
                    <motion.p
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"
                    >
                      {formError || error}
                    </motion.p>
                  )}

                  <motion.button
                    type="submit"
                    disabled={busy}
                    whileTap={reduce ? undefined : { scale: 0.985 }}
                    className="w-full rounded-xl bg-ink-950 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-ink-950/10 transition hover:bg-ink-800 disabled:opacity-60"
                  >
                    {busy
                      ? "Please wait…"
                      : mode === "login"
                        ? "Sign in"
                        : "Create workspace"}
                  </motion.button>
                </form>
              </motion.div>
            </AnimatePresence>

            <p className="mt-5 text-center text-xs text-ink-400">
              Protected by tenant isolation, audit logs, and encrypted transport.
            </p>
          </div>
        </motion.div>
      </div>

      <div className="relative hidden overflow-hidden bg-ink-950 lg:block">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(51,99,255,.35),transparent_55%),radial-gradient(circle_at_75%_75%,rgba(16,185,129,.22),transparent_50%)]" />
        <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(to_right,rgba(255,255,255,.12)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,.12)_1px,transparent_1px)] [background-size:36px_36px]" />
        <div className="relative flex h-full flex-col justify-between p-10">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-white/60">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Clause intelligence
          </div>
          <div className="relative h-[440px]">
            <HeroScene className="h-full w-full" />
          </div>
          <div className="max-w-sm">
            <p className="text-lg font-medium leading-relaxed text-white">
              “Every finding cites the page. Every redline is reviewable. That is the bar.”
            </p>
            <p className="mt-3 text-xs text-white/50">
              Built for legal ops, procurement, and founders who move fast.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field(props: {
  label: string;
  name: string;
  type?: string;
  placeholder?: string;
  required?: boolean;
  minLength?: number;
  autoComplete?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-600">{props.label}</span>
      <input
        name={props.name}
        type={props.type || "text"}
        placeholder={props.placeholder}
        required={props.required}
        minLength={props.minLength}
        autoComplete={props.autoComplete}
        className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2.5 text-sm text-ink-900 outline-none ring-brand-200 transition focus:ring-2"
      />
    </label>
  );
}