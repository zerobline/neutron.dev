import { create } from "zustand";
import { clearSessionToken } from "@/lib/auth-session";
import { api, type AuthResponse, type User } from "@/lib/api";

function userFromAuthResponse(response: AuthResponse): User {
  return response;
}

interface AuthStore {
  user: User | null;
  loading: boolean;
  error: string | null;
  refreshMe: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AUTH_TTL_MS = 5_000;
let lastAuthCheck = 0;
let inflight: Promise<void> | null = null;

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  loading: false,
  error: null,

  refreshMe: async () => {
    if (Date.now() - lastAuthCheck < AUTH_TTL_MS) return;
    if (inflight) return inflight;
    clearSessionToken();
    const p = (async () => {
      set({ loading: true, error: null });
      try {
        const user = await api.me();
        set({ user, loading: false });
      } catch {
        set({ user: null, loading: false });
      } finally {
        lastAuthCheck = Date.now();
        inflight = null;
      }
    })();
    inflight = p;
    return p;
  },

  login: async (email, password) => {
    set({ loading: true, error: null });
    try {
      const response = await api.login({ email, password });
      clearSessionToken();
      set({ user: userFromAuthResponse(response), loading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Could not log in.", loading: false });
      throw error;
    }
  },

  register: async (email, password, displayName) => {
    set({ loading: true, error: null });
    try {
      const response = await api.register({ email, password, display_name: displayName || null });
      clearSessionToken();
      set({ user: userFromAuthResponse(response), loading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Could not create account.", loading: false });
      throw error;
    }
  },

  logout: async () => {
    set({ loading: true, error: null });
    try {
      await api.logout();
    } finally {
      clearSessionToken();
      set({ user: null, loading: false });
    }
  },
}));
