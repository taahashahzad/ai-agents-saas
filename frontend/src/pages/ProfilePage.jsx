import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useBusiness } from '../hooks/useBusiness';
import Button from '../components/Button';
import Card from '../components/Card';
import EmptyState from '../components/EmptyState';
import ErrorAlert from '../components/ErrorAlert';
import RoleBadge from '../components/RoleBadge';
import Spinner from '../components/Spinner';
import { getBusinessId } from '../utils/permissions';

function Field({ label, children }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-1 text-sm text-slate-900">{children}</dd>
    </div>
  );
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const { user, profile } = useAuth();
  const {
    businesses,
    loading,
    error,
    activeBusiness,
    activeBusinessId,
    role,
    isSystemAdmin,
    getRoleFor,
    switchBusiness,
    refreshBusinesses,
  } = useBusiness();

  const name = profile?.full_name || profile?.name || user?.displayName || '—';
  const email = profile?.email || user?.email || '—';

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Profile</h1>

      <Card>
        <dl className="grid gap-5 sm:grid-cols-2">
          <Field label="Name">{name}</Field>
          <Field label="Email">{email}</Field>
          {isSystemAdmin && (
            <Field label="Platform role">
              <RoleBadge role="system_admin" />
            </Field>
          )}
          <Field label="Current business">{activeBusiness?.name || '—'}</Field>
          <Field label="Your role in current business">
            {role ? <RoleBadge role={role} /> : '—'}
          </Field>
        </dl>
      </Card>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-900">Your businesses</h2>
        {loading ? (
          <Spinner label="Loading businesses..." />
        ) : error ? (
          <ErrorAlert message={error} onRetry={() => refreshBusinesses()} />
        ) : businesses.length === 0 ? (
          <EmptyState
            title="No businesses yet"
            description="Create a business or accept an invitation to get started."
          />
        ) : (
          <Card padded={false}>
            <ul className="divide-y divide-slate-100">
              {businesses.map((b) => {
                const id = getBusinessId(b);
                const active = id === activeBusinessId;
                return (
                  <li key={id} className="flex items-center justify-between gap-3 px-5 py-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{b.name}</p>
                      <div className="mt-1 flex items-center gap-2">
                        <RoleBadge role={getRoleFor(b)} />
                        {active && <span className="text-xs font-medium text-indigo-600">Active</span>}
                      </div>
                    </div>
                    {!active && (
                      <Button
                        variant="secondary"
                        onClick={() => {
                          switchBusiness(id);
                          navigate('/');
                        }}
                        className="!px-3 !py-1.5 text-xs"
                      >
                        Switch
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>
        )}
      </section>
    </div>
  );
}
