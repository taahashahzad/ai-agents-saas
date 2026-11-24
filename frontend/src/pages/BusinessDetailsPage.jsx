import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useBusiness } from '../hooks/useBusiness';
import { archiveBusiness, getBusiness, updateBusiness } from '../services/businessService';
import BusinessForm from '../components/BusinessForm';
import Button from '../components/Button';
import Card from '../components/Card';
import ConfirmDialog from '../components/ConfirmDialog';
import ErrorAlert from '../components/ErrorAlert';
import RoleBadge from '../components/RoleBadge';
import Spinner from '../components/Spinner';
import { businessTypeLabel, formatDate } from '../utils/constants';
import { getErrorMessage } from '../utils/errors';
import { getBusinessId, getPermissions } from '../utils/permissions';

function Field({ label, children }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-1 text-sm text-slate-900">{children}</dd>
    </div>
  );
}

export default function BusinessDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, profile } = useAuth();
  const { businesses, getRoleFor, refreshBusinesses } = useBusiness();

  const [business, setBusiness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState('');

  // The role for THIS business, from the backend-provided membership list.
  const membership = businesses.find((b) => getBusinessId(b) === id);
  const role = getRoleFor(membership || business);
  const permissions = getPermissions(role);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      setBusiness(await getBusiness(id));
    } catch (err) {
      setBusiness(null);
      const status = err.response?.status;
      setLoadError(
        status === 404
          ? 'Business not found, or you no longer have access to it.'
          : getErrorMessage(err, 'Failed to load business.')
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    // Drop anything from a previously viewed business before loading this one.
    setBusiness(null);
    setEditing(false);
    load();
  }, [load]);

  const handleSave = async (values) => {
    setSaving(true);
    setSaveError('');
    try {
      const updated = await updateBusiness(id, values);
      setBusiness((prev) => ({ ...prev, ...(updated || values) }));
      setEditing(false);
      refreshBusinesses(); // keep the switcher / dashboard names in sync
    } catch (err) {
      setSaveError(getErrorMessage(err, 'Failed to update business.'));
    } finally {
      setSaving(false);
    }
  };

  const handleArchive = async () => {
    setArchiving(true);
    setArchiveError('');
    try {
      await archiveBusiness(id);
      await refreshBusinesses();
      navigate('/', { replace: true });
    } catch (err) {
      setArchiveError(getErrorMessage(err, 'Failed to archive business.'));
      setConfirmOpen(false);
      setArchiving(false);
    }
  };

  if (loading || (!business && !loadError)) return <Spinner label="Loading business..." />;

  if (loadError) {
    return (
      <div className="space-y-4">
        <ErrorAlert message={loadError} onRetry={load} />
        <Link to="/" className="text-sm font-medium text-indigo-600 hover:text-indigo-700">
          &larr; Back to dashboard
        </Link>
      </div>
    );
  }

  const type = business.type || business.business_type;
  const archived = business.archived || business.status === 'archived';
  const owner = business.owner || {};
  const ownerName =
    owner.full_name || owner.name || business.owner_name || (role === 'owner' ? profile?.full_name || user?.displayName : '') || '—';
  const ownerEmail =
    owner.email || business.owner_email || (role === 'owner' ? profile?.email || user?.email : '') || '—';

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to="/" className="text-sm font-medium text-indigo-600 hover:text-indigo-700">
        &larr; Back to dashboard
      </Link>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight text-slate-900">
            {business.name}
          </h1>
          <div className="mt-2 flex items-center gap-2">
            <RoleBadge role={role} />
            {archived && (
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
                Archived
              </span>
            )}
          </div>
        </div>
        {!editing && !archived && (permissions.editBusiness || permissions.archiveBusiness) && (
          <div className="flex gap-3">
            {permissions.editBusiness && (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            {permissions.archiveBusiness && (
              <Button variant="danger" onClick={() => setConfirmOpen(true)}>
                Archive
              </Button>
            )}
          </div>
        )}
      </div>

      <ErrorAlert message={archiveError} />

      {editing ? (
        <Card>
          <h2 className="mb-5 text-base font-semibold text-slate-900">Edit business</h2>
          <BusinessForm
            initialValues={{
              name: business.name || '',
              type: String(type || '').toLowerCase(),
              description: business.description || '',
            }}
            submitLabel="Save changes"
            submitting={saving}
            serverError={saveError}
            onSubmit={handleSave}
            onCancel={() => {
              setEditing(false);
              setSaveError('');
            }}
          />
        </Card>
      ) : (
        <>
          <Card>
            <h2 className="mb-5 text-base font-semibold text-slate-900">Business information</h2>
            <dl className="grid gap-5 sm:grid-cols-2">
              <Field label="Business name">{business.name}</Field>
              <Field label="Business type">{businessTypeLabel(String(type || '').toLowerCase())}</Field>
              <div className="sm:col-span-2">
                <Field label="Description">{business.description || 'No description provided.'}</Field>
              </div>
              <Field label="Created">{formatDate(business.created_at || business.createdAt)}</Field>
              <Field label="Your role">{role ? <RoleBadge role={role} /> : '—'}</Field>
            </dl>
          </Card>
          <Card>
            <h2 className="mb-5 text-base font-semibold text-slate-900">Owner</h2>
            <dl className="grid gap-5 sm:grid-cols-2">
              <Field label="Name">{ownerName}</Field>
              <Field label="Email">{ownerEmail}</Field>
            </dl>
          </Card>
        </>
      )}

      <ConfirmDialog
        open={confirmOpen}
        title="Archive this business?"
        message="Archived businesses are hidden from active use. Make sure you want to continue."
        confirmLabel="Archive"
        loading={archiving}
        onConfirm={handleArchive}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
