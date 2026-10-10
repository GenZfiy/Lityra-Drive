import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, tokens, accessGrant } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    if (!tokens.access && !tokens.refresh) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch (e) {
      // Only log out on a genuine auth failure (401 — token invalid/expired and
      // refresh also failed). A transient network/server error must NOT clear the
      // session or bounce the user to login (e.g. a tunnel blip mid-exam); keep
      // the tokens so the next request/refresh recovers.
      if (e?.status === 401) {
        tokens.clear();
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMe();
  }, [loadMe]);

  const login = async (email, password, product = "learn") => {
    accessGrant.clear();           // every login re-enters the class Access ID
    const t = await api.login(email, password, product);
    tokens.set(t);
    setUser(await api.me());
  };

  const register = async (email, password, full_name, product = "learn") => {
    await api.register(email, password, full_name, product);
    await login(email, password, product);
  };

  // Passwordless sign-in: verify the emailed code and start the session.
  const loginOtp = async (email, code, product = "learn") => {
    accessGrant.clear();
    const t = await api.verifyOtp(email, code, product);
    tokens.set(t);
    setUser(await api.me());
  };

  const logout = async () => {
    try {
      if (tokens.refresh) await api.logout(tokens.refresh);
      await api.exitAccess().catch(() => {});
    } catch {
      /* ignore */
    }
    accessGrant.clear();
    tokens.clear();
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, login, loginOtp, register, logout, reload: loadMe }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
