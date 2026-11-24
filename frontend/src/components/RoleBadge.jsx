import { ROLE_LABELS } from '../utils/permissions';

const ROLE_STYLES = {
  owner: 'bg-purple-50 text-purple-700 ring-purple-200',
  admin: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
  member: 'bg-slate-100 text-slate-600 ring-slate-200',
  system_admin: 'bg-rose-50 text-rose-700 ring-rose-200',
};

const STATUS_STYLES = {
  pending: 'bg-amber-50 text-amber-700 ring-amber-200',
  accepted: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  expired: 'bg-slate-100 text-slate-500 ring-slate-200',
  declined: 'bg-red-50 text-red-700 ring-red-200',
};

const BASE = 'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset';

export default function RoleBadge({ role, className = '' }) {
  if (!role) return null;
  return (
    <span className={`${BASE} ${ROLE_STYLES[role] || ROLE_STYLES.member} ${className}`}>
      {ROLE_LABELS[role] || role}
    </span>
  );
}

export function StatusBadge({ status, className = '' }) {
  const label = status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown';
  return (
    <span className={`${BASE} ${STATUS_STYLES[status] || STATUS_STYLES.expired} ${className}`}>
      {label}
    </span>
  );
}
