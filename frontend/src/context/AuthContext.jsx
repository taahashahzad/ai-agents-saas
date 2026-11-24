import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
} from 'firebase/auth';
import { auth } from '../firebase';
import { syncUser } from '../services/userService';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // Firebase user
  const [profile, setProfile] = useState(null); // Backend profile (best effort)
  const [loading, setLoading] = useState(true);

  const loadProfile = useCallback(async (firebaseUser = auth.currentUser) => {
    if (!firebaseUser) {
      setProfile(null);
      return;
    }

    try {
      const data = await syncUser({
        display_name: firebaseUser.displayName || undefined,
      });
      setProfile(data?.user || data);
    } catch {
      // Backend profile is optional for rendering; fall back to Firebase data.
      setProfile(null);
    }
  }, []);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      if (firebaseUser) {
        await loadProfile(firebaseUser);
      } else {
        setProfile(null);
      }
      setLoading(false);
    });
    return unsubscribe;
  }, [loadProfile]);

  const register = useCallback(async ({ fullName, email, password }) => {
    const credential = await createUserWithEmailAndPassword(auth, email, password);
    await updateProfile(credential.user, { displayName: fullName });
    // Force-refresh so the token carries the display name, then sync backend.
    await credential.user.getIdToken(true);
    const synced = await syncUser({ display_name: fullName });
    setProfile(synced?.user || synced);
    return credential.user;
  }, []);

  const login = useCallback(async ({ email, password }) => {
    const credential = await signInWithEmailAndPassword(auth, email, password);
    return credential.user;
  }, []);

  const logout = useCallback(async () => {
    await signOut(auth);
  }, []);

  const value = useMemo(
    () => ({ user, profile, loading, register, login, logout, refreshProfile: loadProfile }),
    [user, profile, loading, register, login, logout, loadProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
