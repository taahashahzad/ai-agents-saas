import api from '../api';
import { ENDPOINTS } from './endpoints';
import { normalizeRole } from '../utils/permissions';

function toList(data) {
  if (Array.isArray(data)) return data;
  for (const key of ['items', 'members', 'invitations', 'data']) {
    if (Array.isArray(data?.[key])) return data[key];
  }
  return [];
}

export function normalizeMember(m) {
  return {
    uid: m.uid || m.user_id || m.id,
    name: m.full_name || m.name || m.display_name || '',
    email: m.email || '',
    role: normalizeRole(m.role),
    joinedAt: m.joined_at || m.joinedAt || m.created_at || null,
  };
}

export function normalizeInvitation(i) {
  let status = String(i.status || 'pending').toLowerCase();
  const expiresAt = i.expires_at || i.expiresAt || null;
  // Only derived when the backend supplies an expiry timestamp.
  if (status === 'pending' && expiresAt && new Date(expiresAt) < new Date()) {
    status = 'expired';
  }
  return {
    id: i.id || i.invitation_id || i._id,
    businessId: i.business_id || i.businessId || i.business?.id || null,
    businessName: i.business_name || i.businessName || i.business?.name || '',
    email: i.email || i.invitee_email || '',
    role: normalizeRole(i.role),
    status,
    invitedBy:
      i.invited_by_name || i.inviter_name || i.invited_by?.name || i.invited_by?.email || '',
    createdAt: i.created_at || i.createdAt || null,
    expiresAt,
  };
}

// ---- Business members ----
export async function listMembers(businessId) {
  const { data } = await api.get(ENDPOINTS.members(businessId));
  return toList(data).map(normalizeMember);
}

export async function removeMember(businessId, uid) {
  await api.delete(ENDPOINTS.member(businessId, uid));
}

export async function changeMemberRole(businessId, uid, role) {
  const { data } = await api.patch(ENDPOINTS.memberRole(businessId, uid), { role });
  return data;
}

// ---- Invitations for one business ----
export async function listBusinessInvitations(businessId) {
  const { data } = await api.get(ENDPOINTS.businessInvitations(businessId));
  return toList(data).map(normalizeInvitation);
}

export async function inviteMember(businessId, { email, role }) {
  const { data } = await api.post(ENDPOINTS.businessInvitations(businessId), { email, role });
  return data;
}

// ---- Invitations addressed to the signed-in user ----
export async function listMyInvitations() {
  const { data } = await api.get(ENDPOINTS.myInvitations);
  return toList(data).map(normalizeInvitation);
}

export async function acceptInvitation(id) {
  const { data } = await api.post(ENDPOINTS.acceptInvitation(id));
  return data;
}

export async function declineInvitation(id) {
  const { data } = await api.post(ENDPOINTS.declineInvitation(id));
  return data;
}
