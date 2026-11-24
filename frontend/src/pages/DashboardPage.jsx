import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useBusiness } from '../hooks/useBusiness';
import Button from '../components/Button';
import Card from '../components/Card';
import StatCard from '../components/StatCard';
import BusinessCard from '../components/BusinessCard';
import EmptyState from '../components/EmptyState';
import ErrorAlert from '../components/ErrorAlert';
import RoleBadge from '../components/RoleBadge';
import Spinner from '../components/Spinner';
import { getBusinessId } from '../utils/permissions';

export default function DashboardPage() {
  const { user, profile } = useAuth();
  const {
    businesses,
    loading,
    error,
    refreshBusinesses,
    activeBusiness,
    activeBusinessId,
    role,
    permissions,
    isSystemAdmin,
    pendingInvitationCount,
  } = useBusiness();

  const name = profile?.full_name || profile?.name || user?.displayName || 'there';
  const email = profile?.email || user?.email;
  const activeCount = businesses.filter((b) => !(b.archived || b.status === 'archived')).length;

  const createButton = (
    <Link to="/businesses/new">
      <Button>Create business</Button>
    </Link>
  );

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Welcome, {name}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Here&apos;s an overview of your businesses.
          </p>
        </div>
        <div className="flex gap-3">
          {permissions.viewTeam && activeBusiness && (
            <Link to="/team">
              <Button variant="secondary">Manage team</Button>
            </Link>
          )}
          {createButton}
        </div>
      </div>

      {pendingInvitationCount > 0 && (
        <Link
          to="/invitations"
          className="flex items-center justify-between rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-700 hover:bg-indigo-100"
        >
          <span>
            You have {pendingInvitationCount} pending invitation{pendingInvitationCount > 1 ? 's' : ''}.
          </span>
          <span className="font-medium">View &rarr;</span>
        </Link>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          label="Total businesses"
          value={loading ? '—' : businesses.length}
          hint={loading ? undefined : `${activeCount} active`}
        />
        <Card>
          <p className="text-sm font-medium text-slate-500">Active business</p>
          {activeBusiness ? (
            <>
              <p className="mt-2 truncate text-xl font-semibold tracking-tight text-slate-900">
                {activeBusiness.name}
              </p>
              <div className="mt-2">
                <RoleBadge role={role} />
              </div>
            </>
          ) : (
            <p className="mt-2 text-sm text-slate-400">{loading ? '—' : 'None selected'}</p>
          )}
        </Card>
        <Card>
          <p className="text-sm font-medium text-slate-500">Profile</p>
          <dl className="mt-3 space-y-3 text-sm">
            <div>
              <dt className="text-xs text-slate-400">Full name</dt>
              <dd className="font-medium text-slate-900">{profile?.full_name || profile?.name || user?.displayName || '—'}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-400">Email</dt>
              <dd className="truncate font-medium text-slate-900">{email || '—'}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <section>
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Your businesses</h2>
        {loading ? (
          <Spinner label="Loading businesses..." />
        ) : error ? (
          <ErrorAlert message={error} onRetry={() => refreshBusinesses()} />
        ) : businesses.length === 0 ? (
          <EmptyState
            title="No businesses yet"
            description="Create your first business, or accept an invitation to join an existing one."
            action={createButton}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {businesses.map((b) => (
              <BusinessCard
                key={getBusinessId(b)}
                business={b}
                active={getBusinessId(b) === activeBusinessId}
                isSystemAdmin={isSystemAdmin}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
