import { createContext, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { listBusinesses } from '../services/businessService';
import { listMyInvitations } from '../services/memberService';
import { getErrorMessage } from '../utils/errors';
import {
  effectiveRole,
  getBusinessId,
  getBusinessRole,
  getPermissions,
  isSystemAdmin,
} from '../utils/permissions';

export const BusinessContext = createContext(null);

// Only the selected business ID is remembered locally (per user). The role is
// NEVER stored: it always comes from the backend business list.
const storageKey = (uid) => `activeBusinessId:${uid}`;
function readStoredId(uid) {
  try {
    return localStorage.getItem(storageKey(uid));
  } catch {
    return null;
  }
}
function writeStoredId(uid, id) {
  try {
    if (id) localStorage.setItem(storageKey(uid), id);
    else localStorage.removeItem(storageKey(uid));
  } catch {
    /* storage unavailable: selection just won't persist */
  }
}

const EMPTY = { uid: null, businesses: [], activeId: null, error: '' };

export function BusinessProvider({ children }) {
  const { user, profile } = useAuth();
  const uid = user?.uid || null;

  const [state, setState] = useState(EMPTY);
  const [pending, setPending] = useState({ uid: null, count: 0 });
  const [refreshing, setRefreshing] = useState(false);

  const stateRef = useRef(state);
  stateRef.current = state;
  const requestRef = useRef(0);

  const refreshBusinesses = useCallback(
    async (preferredId) => {
      if (!uid) return;
      const requestId = ++requestRef.current;
      setRefreshing(true);
      try {
        const items = await listBusinesses();
        if (requestId !== requestRef.current) return; // a newer request superseded this one
        const known = (id) => id && items.some((b) => getBusinessId(b) === id);
        const previous = stateRef.current.uid === uid ? stateRef.current.activeId : null;
        const next =
          [preferredId, previous, readStoredId(uid)].find(known) ||
          (items[0] ? getBusinessId(items[0]) : null);
        writeStoredId(uid, next);
        setState({ uid, businesses: items, activeId: next, error: '' });
      } catch (err) {
        if (requestId !== requestRef.current) return;
        const message = getErrorMessage(err, 'Failed to load your businesses.');
        setState((prev) =>
          prev.uid === uid ? { ...prev, error: message } : { uid, businesses: [], activeId: null, error: message }
        );
      } finally {
        if (requestId === requestRef.current) setRefreshing(false);
      }
    },
    [uid]
  );

  const refreshInvitations = useCallback(async () => {
    if (!uid) return;
    try {
      const items = await listMyInvitations();
      setPending({ uid, count: items.filter((i) => i.status === 'pending').length });
    } catch {
      /* the badge is non-critical; the Invitations page shows real errors */
    }
  }, [uid]);

  // Reset everything when the signed-in user changes, then load that user's data.
  useEffect(() => {
    if (!uid) {
      requestRef.current += 1;
      setState(EMPTY);
      setPending({ uid: null, count: 0 });
      return;
    }
    refreshBusinesses();
    refreshInvitations();
  }, [uid, refreshBusinesses, refreshInvitations]);

  const switchBusiness = useCallback(
    (id) => {
      const current = stateRef.current;
      if (!uid || current.uid !== uid) return;
      if (!current.businesses.some((b) => getBusinessId(b) === id)) return;
      writeStoredId(uid, id);
      setState({ ...current, activeId: id });
    },
    [uid]
  );

  const ready = !uid || state.uid === uid;
  const systemAdmin = isSystemAdmin(profile);

  const value = useMemo(() => {
    const businesses = ready ? state.businesses : [];
    const activeBusinessId = ready ? state.activeId : null;
    const activeBusiness = businesses.find((b) => getBusinessId(b) === activeBusinessId) || null;
    const getRoleFor = (business) => effectiveRole(getBusinessRole(business), systemAdmin);
    const role = activeBusiness ? getRoleFor(activeBusiness) : null;

    return {
      businesses,
      loading: !ready,
      refreshing,
      error: ready ? state.error : '',
      activeBusiness,
      activeBusinessId,
      role,
      permissions: getPermissions(role),
      isSystemAdmin: systemAdmin,
      getRoleFor,
      pendingInvitationCount: pending.uid === uid ? pending.count : 0,
      switchBusiness,
      refreshBusinesses,
      refreshInvitations,
    };
  }, [
    ready,
    state,
    refreshing,
    systemAdmin,
    pending,
    uid,
    switchBusiness,
    refreshBusinesses,
    refreshInvitations,
  ]);

  return <BusinessContext.Provider value={value}>{children}</BusinessContext.Provider>;
}
