import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useBusiness } from '../hooks/useBusiness';
import BusinessInfoTab from '../components/knowledge/BusinessInfoTab';
import DocumentsTab from '../components/knowledge/DocumentsTab';
import Button from '../components/Button';
import EmptyState from '../components/EmptyState';
import Notice from '../components/Notice';
import RoleBadge from '../components/RoleBadge';
import Spinner from '../components/Spinner';
import { isArchived } from '../utils/knowledge';

const TABS = [
  { id: 'documents', label: 'Documents' },
  { id: 'info', label: 'Business Information' },
];

export default function KnowledgeBasePage() {
  const { user } = useAuth();
  const { activeBusiness, activeBusinessId, role, permissions, loading } = useBusiness();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'info' ? 'info' : 'documents';

  if (loading) return <Spinner label="Loading..." />;

  if (!activeBusiness) {
    return (
      <EmptyState
        title="No business selected"
        description="Create a business or accept an invitation to use its Knowledge Base."
        action={
          <Link to="/businesses/new">
            <Button>Create business</Button>
          </Link>
        }
      />
    );
  }

  // UI hint only. The backend returns 403 for writes by members and is the real boundary.
  const archived = isArchived(activeBusiness);
  const canWrite = permissions.manageKnowledge && !archived;
  const readOnlyReason = archived
    ? 'This business is archived, so its Knowledge Base is read-only.'
    : 'You have view-only access. Owners and admins can upload documents and manage business information.';

  const selectTab = (id) => setParams(id === 'documents' ? {} : { tab: id }, { replace: true });

  // Both tabs stay mounted (just hidden) so an upload keeps running when you switch tabs.
  // Every child is keyed by the business id, so nothing can be reused across businesses.
  const shared = {
    businessId: activeBusinessId,
    businessName: activeBusiness.name,
    canWrite,
    readOnlyReason: canWrite ? '' : readOnlyReason,
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Knowledge Base</h1>
          <p className="mt-1 text-sm text-slate-500">
            Documents and information your AI agents can learn from for this business.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
          <span className="max-w-[12rem] truncate font-medium text-slate-900">{activeBusiness.name}</span>
          <RoleBadge role={role} />
        </div>
      </div>

      {archived && <Notice type="warning">{readOnlyReason}</Notice>}

      <div className="border-b border-slate-200">
        <nav className="-mb-px flex gap-6" role="tablist" aria-label="Knowledge Base sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => selectTab(t.id)}
              className={`border-b-2 px-1 pb-3 text-sm font-medium transition ${
                tab === t.id
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      <div role="tabpanel" hidden={tab !== 'documents'}>
        <DocumentsTab key={activeBusinessId} {...shared} currentUid={user?.uid} />
      </div>
      <div role="tabpanel" hidden={tab !== 'info'}>
        <BusinessInfoTab
          key={activeBusinessId}
          {...shared}
          businessType={activeBusiness.type || activeBusiness.business_type}
        />
      </div>
    </div>
  );
}
