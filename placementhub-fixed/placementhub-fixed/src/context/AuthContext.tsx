import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { api, ApiError, setUnauthenticatedHandler } from '../lib/api';
import type { AuthUser, Lookups } from '../types';

interface AuthCtx {
  user: AuthUser | null;
  loading: boolean;
  lookups: Lookups;
  can: (perm: string) => boolean;
  login: (body: Record<string, unknown>) => Promise<AuthUser>;
  logout: () => Promise<void>;
  setUser: (u: AuthUser) => void;
  refreshLookups: () => Promise<void>;
  sessionExpired: boolean;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [lookups, setLookups] = useState<Lookups>({});
  const [sessionExpired, setExpired] = useState(false);
  const userRef = useRef<AuthUser | null>(null);
  userRef.current = user;

  const refreshLookups = useCallback(async () => {
    try { setLookups(await api.get<Lookups>('/api/lookups')); } catch { /* password change pending etc. */ }
  }, []);

  useEffect(() => {
    api.get<{ user: AuthUser }>('/api/auth/me')
      .then((r) => { setUserState(r.user); if (!r.user.mustChangePassword) refreshLookups(); })
      .catch(() => setUserState(null))
      .finally(() => setLoading(false));
    // Only a user who was actually signed in can have a "session that expired" (state updaters must stay side-effect free).
    setUnauthenticatedHandler(() => { if (userRef.current) { setExpired(true); setUserState(null); setLookups({}); } });
  }, [refreshLookups]);

  const value = useMemo<AuthCtx>(() => ({
    user, loading, lookups, sessionExpired,
    can: (p) => !!user?.permissions.includes(p),
    login: async (body) => {
      const r = await api.post<{ user: AuthUser }>('/api/auth/login', body);
      // Make sure the browser really kept the session cookie. If it did not (blocked cookies, an embedded preview,
      // a stale Secure cookie flag), say so now instead of bouncing back to the login page as "session expired".
      try { await api.get('/api/auth/me'); }
      catch (e) {
        if ((e as ApiError).status === 401) throw new ApiError('Your password was accepted, but the browser did not keep the sign-in cookie. Allow cookies for this site, open the app directly in its own tab (not inside an embedded preview), then try again.', 401, 'cookie_blocked');
      }
      setExpired(false);
      setUserState(r.user);
      if (!r.user.mustChangePassword) refreshLookups();
      return r.user;
    },
    logout: async () => { try { await api.post('/api/auth/logout'); } catch { /* ignore */ } setUserState(null); setLookups({}); window.location.hash = ''; },
    setUser: (u) => { setUserState(u); if (!u.mustChangePassword) refreshLookups(); },
    refreshLookups,
  }), [user, loading, lookups, sessionExpired, refreshLookups]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAuth = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error('useAuth outside AuthProvider');
  return c;
};
