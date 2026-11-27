"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, getToken, setToken } from "@/lib/api";
import type { UserOut } from "@/lib/types";

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

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      await api.login(email, password);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      throw err;
    }
  }, [refresh]);

  const register = useCallback(async (input: {
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
  }, [refresh]);

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
  const [mode, setMode] = useState<"login" | "register">("login");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

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
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center">
      <div className="rounded-2xl border border-ink-200 bg-white p-6 shadow-card">
        <h1 className="text-xl font-semibold text-ink-900">
          {mode === "login" ? "Sign in to ClauseGuard" : "Create your workspace"}
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Every finding is page-cited and exportable as tracked changes.
        </p>
        <form onSubmit={submit} className="mt-5 space-y-3">
          {mode === "register" && (
            <>
              <Field label="Company" name="tenant_name" placeholder="Acme Legal" required />
              <Field label="Full name" name="full_name" placeholder="Ada Lovelace" />
            </>
          )}
          <Field label="Work email" name="email" type="email" placeholder="you@company.com" required />
          <Field
            label="Password"
            name="password"
            type="password"
            placeholder="At least 10 characters"
            required
            minLength={10}
          />
          {(formError || error) && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{formError || error}</p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-60"
          >
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create workspace"}
          </button>
        </form>
        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="mt-4 w-full text-center text-sm font-medium text-brand-700 hover:underline"
        >
          {mode === "login" ? "Need an account? Register" : "Already registered? Sign in"}
        </button>
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
        className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 outline-none ring-brand-200 focus:ring-2"
      />
    </label>
  );
}