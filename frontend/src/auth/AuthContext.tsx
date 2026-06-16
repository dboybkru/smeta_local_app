import { createContext, useContext, useEffect, useState } from "react";
import { api } from "../api/client";

export type User = {
  id: number;
  email: string;
  name: string;
  role: string;
  status: string;
  is_superuser: boolean;
  org_id: number | null;
  org_name: string | null;
};

type AuthState = {
  user: User | null | undefined; // undefined = загрузка
  loginWithPassword: (email: string, password: string) => Promise<void>;
  reload: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  async function loadMe() {
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      setUser(null);
    }
  }

  useEffect(() => {
    void loadMe();
  }, []);

  async function loginWithPassword(email: string, password: string) {
    setUser(await api<User>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }));
  }

  async function reload() {
    await loadMe();
  }

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      // ignore errors — clear local state anyway
    }
    setUser(null);
  }

  return (
    <AuthCtx.Provider value={{ user, loginWithPassword, reload, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
