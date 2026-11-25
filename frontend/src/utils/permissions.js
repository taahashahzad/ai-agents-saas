/**
 * Role + permission helpers.
 *
 * IMPORTANT: these drive UI visibility only. The backend is the real security
 * boundary and must re-check every action. Roles are always read per business
 * from backend data (never from localStorage, never assumed global).
 */

export const BUSINESS_ROLES = ['owner', 'admin', 'member'];

export const ROLE_LABELS = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
  system_admin: 'System Admin',
};

export function normalizeRole(role) {
  return String(role || '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');
}

export function getBusinessId(business) {
  return business?.id || business?._id || business?.business_id || null;
}

/**
 * The signed-in user's role in ONE business, as reported by GET /api/v1/businesses.
 * Field name is an assumption until the backend schema is confirmed; the common
 * shapes are handled here in one place.
 */
export function getBusinessRole(business) {
  if (!business) return '';
  return normalizeRole(
    business.role ||
      business.my_role ||
      business.membership_role ||
      business.membership?.role ||
      ''
  );
}

/** Platform-level role, from GET /api/v1/users/me. Not a business membership role. */
export function isSystemAdmin(profile) {
  if (!profile) return false;
  return (
    profile.is_system_admin === true ||
    normalizeRole(profile.role) === 'system_admin' ||
    normalizeRole(profile.platform_role) === 'system_admin'
  );
}

/**
 * Effective role for the UI in one business.
 * A real membership role always wins. A system admin with no membership in
 * that business is shown as 'system_admin'.
 */
export function effectiveRole(membershipRole, systemAdmin) {
  const role = normalizeRole(membershipRole);
  if (BUSINESS_ROLES.includes(role)) return role;
  return systemAdmin ? 'system_admin' : null;
}

export function getPermissions(role) {
  const full = role === 'owner' || role === 'system_admin';
  const admin = role === 'admin';
  const manage = full || admin;

  let inviteRoles = [];
  if (full) inviteRoles = ['admin', 'member'];
  else if (admin) inviteRoles = ['member'];

  return {
    role,
    viewTeam: manage,
    viewInvitations: manage,
    inviteMembers: manage,
    inviteRoles,
    changeRoles: full,
    editBusiness: manage,
    archiveBusiness: full,
    // Knowledge Base: everyone can view; only owner/admin can upload, delete and edit.
    manageKnowledge: manage,
    manageAgents: manage,
  };
}

/** Can the current user remove this member? (UI hint only.) */
export function canRemoveMember(permissions, member, currentUid) {
  if (!permissions.viewTeam) return false;
  if (!member || member.uid === currentUid) return false; // no self-removal / self-demotion paths
  if (member.role === 'owner') return false;
  if (permissions.role === 'admin') return member.role === 'member'; // admins remove members only
  return true; // owner / system admin: admins and members
}

/** Roles this member could be changed to by the current user. */
export function roleChangeOptions(permissions, member, currentUid) {
  if (!permissions.changeRoles) return [];
  if (!member || member.uid === currentUid) return [];
  if (member.role === 'owner') return [];
  return ['admin', 'member'].filter((r) => r !== member.role);
}
