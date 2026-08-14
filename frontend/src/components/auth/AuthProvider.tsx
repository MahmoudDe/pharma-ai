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
import { UNAUTHORIZED_EVENT, getAuthToken, setAuthToken } from "@/lib/api";
import {
  deleteAccount as deleteAccountRequest,
  fetchCurrentUser,
  loginAccount,
  logoutAccount,
  registerAccount,
  updateAccountPassword,
  updateAccountProfile,
  type AuthUser,
} from "@/lib/auth";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    name: string,
    email: string,
    password: string,
    passwordConfirmation: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (name: string, email: string) => Promise<void>;
  updatePassword: (
    currentPassword: string,
    password: string,
    passwordConfirmation: string,
  ) => Promise<void>;
  deleteAccount: (password: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getAuthToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await fetchCurrentUser());
    } catch {
      setAuthToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setLoading(false);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const payload = await loginAccount(email, password);
    setUser(payload.user);
  }, []);

  const register = useCallback(
    async (name: string, email: string, password: string, passwordConfirmation: string) => {
      const payload = await registerAccount(name, email, password, passwordConfirmation);
      setUser(payload.user);
    },
    [],
  );

  const logout = useCallback(async () => {
    await logoutAccount();
    setUser(null);
  }, []);

  const updateProfile = useCallback(async (name: string, email: string) => {
    setUser(await updateAccountProfile(name, email));
  }, []);

  const updatePassword = useCallback(
    async (currentPassword: string, password: string, passwordConfirmation: string) => {
      const payload = await updateAccountPassword(
        currentPassword,
        password,
        passwordConfirmation,
      );
      setUser(payload.user);
    },
    [],
  );

  const deleteAccount = useCallback(async (password: string) => {
    await deleteAccountRequest(password);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login,
      register,
      logout,
      updateProfile,
      updatePassword,
      deleteAccount,
    }),
    [user, loading, login, register, logout, updateProfile, updatePassword, deleteAccount],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
