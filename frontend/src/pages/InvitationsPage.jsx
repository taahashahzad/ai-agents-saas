import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useBusiness } from '../hooks/useBusiness';
import { acceptInvitation, declineInvitation, listMyInvitations } from '../services/memberService';
import Button from '../components/Button';
import Card from '../components/Card';
import EmptyState from '../components/EmptyState';
import ErrorAlert from '../components/ErrorAlert';
import RoleBadge, { StatusBadge } from '../components/RoleBadge';
import Spinner from '../components/Spinner';
import { formatDate } from '../utils/constants';
import { getErrorMessage } from '../utils/errors';

export default function InvitationsPage() {
  const navigate = useNavigate();
  const { refreshBusinesses, refreshInvitations, switchBusiness } = useBusiness();

  const [invitations, setInvitations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [actionError, setActionError] = useState('');
  const [accepted, setAccepted] = useState(null); // { businessId, businessName }
  const reqRef = useRef(0);

  const load = useCallback(async () => {
    const id = ++reqRef.current;
    setLoading(true);
    setError('');
    try {
      const list = await listMyInvitations();
      if (id === reqRef.current) setInvitations(list);
    } catch (err) {
      if (id !== reqRef.current) return;
      setInvitations([]);
      setError(getErrorMessage(err, 'Failed to load invitations.'));
    } finally {
      if (id === reqRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    return () => {
      reqRef.current += 1;
    };
  }, [load]);

  const handleAccept = async (inv) => {
    setBusyId(inv.id);
    setActionError('');
    setAccepted(null);
    try {
      await acceptInvitation(inv.id);
      // The accepted business must now appear in the user's business list.
      await refreshBusinesses();
      setAccepted({ businessId: inv.businessId, businessName: inv.businessName });
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to accept invitation.'));
    } finally {
      setBusyId(null);
      await load(); // reflect the true server state, including expired/invalid ones
      refreshInvitations();
    }
  };

  const handleDecline = async (inv) => {
    setBusyId(inv.id);
    setActionError('');
    setAccepted(null);
    try {
      await declineInvitation(inv.id);
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to decline invitation.'));
    } finally {
      setBusyId(null);
      await load();
      refreshInvitations();
    }
  };

  const openAccepted = () => {
    if (accepted?.businessId) switchBusiness(accepted.businessId);
    navigate('/');
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Invitations</h1>
        <p className="mt-1 text-sm text-slate-500">Businesses that have invited you to join.</p>
      </div>

      {accepted && (
        <div role="status" className="flex flex-col gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 sm:flex-row sm:items-center sm:justify-between">
          <span>
            You joined{accepted.businessName ? ` ${accepted.businessName}` : ' the business'}.
          </span>
          {accepted.businessId && (
            <button type="button" onClick={openAccepted} className="font-medium underline">
              Open this business
            </button>
          )}
        </div>
      )}
      <ErrorAlert message={actionError} />

      {loading ? (
        <Spinner label="Loading invitations..." />
      ) : error ? (
        <ErrorAlert message={error} onRetry={load} />
      ) : invitations.length === 0 ? (
        <EmptyState
          title="No invitations"
          description="When someone invites you to a business, it will show up here."
        />
      ) : (
        <div className="space-y-3">
          {invitations.map((inv) => {
            const pending = inv.status === 'pending';
            return (
              <Card key={inv.id} className="!p-5">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate text-base font-semibold text-slate-900">
                        {inv.businessName || 'Business invitation'}
                      </h3>
                      <RoleBadge role={inv.role} />
                      <StatusBadge status={inv.status} />
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {inv.invitedBy ? `Invited by ${inv.invitedBy} · ` : ''}
                      {formatDate(inv.createdAt)}
                      {inv.expiresAt ? ` · Expires ${formatDate(inv.expiresAt)}` : ''}
                    </p>
                    {inv.status === 'expired' && (
                      <p className="mt-1 text-xs text-slate-500">
                        This invitation has expired. Ask the business owner or an admin to send a new one.
                      </p>
                    )}
                  </div>
                  {pending && (
                    <div className="flex shrink-0 gap-2">
                      <Button
                        variant="secondary"
                        onClick={() => handleDecline(inv)}
                        disabled={busyId !== null}
                      >
                        Decline
                      </Button>
                      <Button
                        onClick={() => handleAccept(inv)}
                        loading={busyId === inv.id}
                        disabled={busyId !== null}
                      >
                        Accept
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
