import { createContext, useContext, useEffect, useState } from "react";
import { api, clearTokens, getTokens, setTokens } from "../api/client";

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
  acceptTokens: (access: string, refresh: string) => Promise<void>;
  logout: () => void;
};

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  async function loadMe() {
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      clearTokens();
      setUser(null);
    }
  }

  useEffect(() => {
    if (getTokens().access) void loadMe();
    else setUser(null);
  }, []);

  async function loginWithPassword(email: string, password: string) {
    const pair = await api<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setTokens(pair.access_token, pair.refresh_token);
    await loadMe();
  }

  async function acceptTokens(access: string, refresh: string) {
    setTokens(access, refresh);
    await loadMe();
  }

  function logout() {
    clearTokens();
    setUser(null);
  }

  return (
    <AuthCtx.Provider value={{ user, loginWithPassword, acceptTokens, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
