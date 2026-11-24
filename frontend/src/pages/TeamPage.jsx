import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useBusiness } from '../hooks/useBusiness';
import {
  changeMemberRole,
  listBusinessInvitations,
  listMembers,
  removeMember,
} from '../services/memberService';
import AccessDenied from '../components/AccessDenied';
import Button from '../components/Button';
import Card from '../components/Card';
import ConfirmDialog from '../components/ConfirmDialog';
import EmptyState from '../components/EmptyState';
import ErrorAlert from '../components/ErrorAlert';
import InviteModal from '../components/InviteModal';
import RoleBadge, { StatusBadge } from '../components/RoleBadge';
import Spinner from '../components/Spinner';
import { formatDate } from '../utils/constants';
import { getErrorMessage } from '../utils/errors';
import { ROLE_LABELS, canRemoveMember, roleChangeOptions } from '../utils/permissions';

export default function TeamPage() {
  const { user } = useAuth();
  const { activeBusiness, activeBusinessId, permissions, loading: businessLoading } = useBusiness();
  const businessId = activeBusinessId;
  const canView = permissions.viewTeam;

  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [membersError, setMembersError] = useState('');

  const [invitations, setInvitations] = useState([]);
  const [invitationsLoading, setInvitationsLoading] = useState(true);
  const [invitationsError, setInvitationsError] = useState('');

  const [inviteOpen, setInviteOpen] = useState(false);
  const [toRemove, setToRemove] = useState(null);
  const [removing, setRemoving] = useState(false);
  const [busyUid, setBusyUid] = useState(null);
  const [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState('');

  const membersReq = useRef(0);
  const invitationsReq = useRef(0);

  const loadMembers = useCallback(async () => {
    if (!businessId || !canView) return;
    const id = ++membersReq.current;
    setMembersLoading(true);
    setMembersError('');
    try {
      const list = await listMembers(businessId);
      if (id === membersReq.current) setMembers(list);
    } catch (err) {
      if (id !== membersReq.current) return;
      setMembers([]);
      setMembersError(getErrorMessage(err, 'Failed to load members.'));
    } finally {
      if (id === membersReq.current) setMembersLoading(false);
    }
  }, [businessId, canView]);

  const loadInvitations = useCallback(async () => {
    if (!businessId || !permissions.viewInvitations) return;
    const id = ++invitationsReq.current;
    setInvitationsLoading(true);
    setInvitationsError('');
    try {
      const list = await listBusinessInvitations(businessId);
      if (id === invitationsReq.current) setInvitations(list);
    } catch (err) {
      if (id !== invitationsReq.current) return;
      setInvitations([]);
      setInvitationsError(getErrorMessage(err, 'Failed to load invitations.'));
    } finally {
      if (id === invitationsReq.current) setInvitationsLoading(false);
    }
  }, [businessId, permissions.viewInvitations]);

  useEffect(() => {
    loadMembers();
    loadInvitations();
    return () => {
      // Invalidate in-flight requests so a late response can't land after a switch.
      membersReq.current += 1;
      invitationsReq.current += 1;
    };
  }, [loadMembers, loadInvitations]);

  if (businessLoading) return <Spinner label="Loading..." />;

  if (!activeBusiness) {
    return (
      <EmptyState
        title="No business selected"
        description="Create a business or accept an invitation to manage a team."
        action={
          <Link to="/businesses/new">
            <Button>Create business</Button>
          </Link>
        }
      />
    );
  }

  if (!canView) {
    return (
      <AccessDenied
        title="Team management is restricted"
        message="Only owners and admins can view and manage the team of this business."
      />
    );
  }

  const handleRoleChange = async (member, newRole) => {
    setBusyUid(member.uid);
    setActionError('');
    setNotice('');
    try {
      await changeMemberRole(businessId, member.uid, newRole);
      setNotice(`${member.name || member.email} is now ${ROLE_LABELS[newRole]}.`);
      await loadMembers();
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to change role.'));
    } finally {
      setBusyUid(null);
    }
  };

  const handleRemove = async () => {
    if (!toRemove) return;
    setRemoving(true);
    setActionError('');
    setNotice('');
    try {
      await removeMember(businessId, toRemove.uid);
      setNotice(`${toRemove.name || toRemove.email} was removed from the business.`);
      setToRemove(null);
      await loadMembers();
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to remove member.'));
      setToRemove(null);
    } finally {
      setRemoving(false);
    }
  };

  const handleInvited = async (email) => {
    setInviteOpen(false);
    setActionError('');
    setNotice(`Invitation sent to ${email}.`);
    await loadInvitations();
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Team</h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage who has access to <span className="font-medium text-slate-700">{activeBusiness.name}</span>.
          </p>
        </div>
        {permissions.inviteMembers && (
          <Button onClick={() => setInviteOpen(true)}>Invite member</Button>
        )}
      </div>

      {notice && (
        <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {notice}
        </div>
      )}
      <ErrorAlert message={actionError} />

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-900">
          Members{!membersLoading && !membersError ? ` (${members.length})` : ''}
        </h2>
        {membersLoading ? (
          <Spinner label="Loading members..." />
        ) : membersError ? (
          <ErrorAlert message={membersError} onRetry={loadMembers} />
        ) : members.length === 0 ? (
          <EmptyState title="No members" description="Invite people to collaborate on this business." />
        ) : (
          <Card padded={false} className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Member</th>
                    <th className="px-4 py-3">Email</th>
                    <th className="px-4 py-3">Role</th>
                    <th className="px-4 py-3">Joined</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {members.map((m) => {
                    const isSelf = m.uid === user?.uid;
                    const options = roleChangeOptions(permissions, m, user?.uid);
                    const removable = canRemoveMember(permissions, m, user?.uid);
                    const busy = busyUid === m.uid;
                    return (
                      <tr key={m.uid}>
                        <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">
                          {m.name || '—'}
                          {isSelf && <span className="ml-2 text-xs font-normal text-slate-400">(you)</span>}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-slate-600">{m.email || '—'}</td>
                        <td className="whitespace-nowrap px-4 py-3">
                          <RoleBadge role={m.role} />
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-slate-600">{formatDate(m.joinedAt)}</td>
                        <td className="whitespace-nowrap px-4 py-3">
                          <div className="flex items-center justify-end gap-2">
                            {options.map((role) => (
                              <Button
                                key={role}
                                variant="secondary"
                                loading={busy}
                                disabled={busyUid !== null}
                                onClick={() => handleRoleChange(m, role)}
                                className="!px-3 !py-1.5 text-xs"
                              >
                                {role === 'admin' ? 'Make admin' : 'Make member'}
                              </Button>
                            ))}
                            {removable && (
                              <Button
                                variant="ghost"
                                disabled={busyUid !== null}
                                onClick={() => setToRemove(m)}
                                className="!px-3 !py-1.5 text-xs !text-red-600 hover:!bg-red-50"
                              >
                                Remove
                              </Button>
                            )}
                            {options.length === 0 && !removable && (
                              <span className="text-xs text-slate-400">—</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-900">Invitations</h2>
        {invitationsLoading ? (
          <Spinner label="Loading invitations..." />
        ) : invitationsError ? (
          <ErrorAlert message={invitationsError} onRetry={loadInvitations} />
        ) : invitations.length === 0 ? (
          <EmptyState
            title="No invitations"
            description="Invitations you send will appear here with their status."
          />
        ) : (
          <Card padded={false} className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Email</th>
                    <th className="px-4 py-3">Role</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Sent</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {invitations.map((inv) => (
                    <tr key={inv.id}>
                      <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">{inv.email}</td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <RoleBadge role={inv.role} />
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <StatusBadge status={inv.status} />
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-slate-600">{formatDate(inv.createdAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </section>

      {inviteOpen && (
        <InviteModal
          businessId={businessId}
          businessName={activeBusiness.name}
          allowedRoles={permissions.inviteRoles}
          onClose={() => setInviteOpen(false)}
          onInvited={handleInvited}
        />
      )}

      <ConfirmDialog
        open={Boolean(toRemove)}
        title="Remove member?"
        message={`${toRemove?.name || toRemove?.email || 'This member'} will lose access to ${activeBusiness.name}.`}
        confirmLabel="Remove"
        loading={removing}
        onConfirm={handleRemove}
        onCancel={() => setToRemove(null)}
      />
    </div>
  );
}
