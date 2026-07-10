import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { ApiError, apiGet, apiPatch, apiPost } from "../lib/api";
import type { BootstrapPayload, LoginPayload } from "../pages/AuthLandingPage";
import { authErrorMessage, loadAuthSnapshot, type AuthUser } from "./authState";

type PasswordChangePayload = {
  current_password: string;
  new_password: string;
};

type AuthContextValue = {
  initialized: boolean | null;
  user: AuthUser | null;
  busy: boolean;
  errorMessage: string | null;
  loadFailed: boolean;
  bootstrap: (payload: BootstrapPayload) => Promise<void>;
  changePassword: (payload: PasswordChangePayload) => Promise<void>;
  clearError: () => void;
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [initialized, setInitialized] = useState<boolean | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  const refresh = useCallback(async () => {
    setLoadFailed(false);
    setErrorMessage(null);
    try {
      const snapshot = await loadAuthSnapshot(apiGet);
      setInitialized(snapshot.initialized);
      setUser(snapshot.user);
    } catch {
      setInitialized(null);
      setUser(null);
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (payload: LoginPayload) => {
    setBusy(true);
    setErrorMessage(null);
    try {
      const nextUser = await apiPost<AuthUser>("/api/v1/auth/login", payload);
      setInitialized(true);
      setUser(nextUser);
    } catch (error) {
      setErrorMessage(requestErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }, []);

  const bootstrap = useCallback(async (payload: BootstrapPayload) => {
    setBusy(true);
    setErrorMessage(null);
    try {
      const nextUser = await apiPost<AuthUser>("/api/v1/auth/bootstrap", payload);
      setInitialized(true);
      setUser(nextUser);
    } catch (error) {
      if (error instanceof ApiError && error.code === "AUTH_BOOTSTRAP_COMPLETE") {
        setInitialized(true);
        setUser(null);
      }
      setErrorMessage(requestErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }, []);

  const logout = useCallback(async () => {
    await apiPost<{ ok: boolean }>("/api/v1/auth/logout");
    setUser(null);
    setInitialized(true);
    setErrorMessage(null);
  }, []);

  const changePassword = useCallback(async (payload: PasswordChangePayload) => {
    await apiPatch<{ ok: boolean }>("/api/v1/auth/password", payload);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      initialized,
      user,
      busy,
      errorMessage,
      loadFailed,
      bootstrap,
      changePassword,
      clearError: () => setErrorMessage(null),
      login,
      logout,
      refresh,
    }),
    [bootstrap, busy, changePassword, errorMessage, initialized, loadFailed, login, logout, refresh, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

function requestErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return authErrorMessage(error.code);
  }
  return "暂时无法连接系统，请检查服务状态后重试。";
}
