import { Link } from 'react-router-dom';
import Card from './Card';
import RoleBadge from './RoleBadge';
import { businessTypeLabel, formatDate } from '../utils/constants';
import { effectiveRole, getBusinessRole } from '../utils/permissions';

const TYPE_STYLES = {
  restaurant: 'bg-orange-50 text-orange-700',
  clinic: 'bg-emerald-50 text-emerald-700',
  school: 'bg-sky-50 text-sky-700',
};

export default function BusinessCard({ business, active = false, isSystemAdmin = false }) {
  const type = String(business.type || business.business_type || '').toLowerCase();
  const archived = business.archived || business.status === 'archived';
  const id = business.id || business._id;
  const role = effectiveRole(getBusinessRole(business), isSystemAdmin);

  return (
    <Link to={`/businesses/${id}`} className="block focus:outline-none">
      <Card
        className={`h-full transition hover:border-indigo-300 hover:shadow-md ${
          active ? 'border-indigo-400 ring-1 ring-indigo-200' : ''
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <h3 className="truncate text-base font-semibold text-slate-900">{business.name}</h3>
          <span
            className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
              TYPE_STYLES[type] || 'bg-slate-100 text-slate-600'
            }`}
          >
            {businessTypeLabel(type)}
          </span>
        </div>
        <p className="mt-2 line-clamp-2 min-h-[2.5rem] text-sm text-slate-500">
          {business.description || 'No description provided.'}
        </p>
        <div className="mt-4 flex items-center justify-between gap-2 text-xs text-slate-400">
          <span>Created {formatDate(business.created_at || business.createdAt)}</span>
          <span className="flex items-center gap-1.5">
            {active && <span className="font-medium text-indigo-600">Active</span>}
            {archived && (
              <span className="rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-500">
                Archived
              </span>
            )}
            <RoleBadge role={role} />
          </span>
        </div>
      </Card>
    </Link>
  );
}
