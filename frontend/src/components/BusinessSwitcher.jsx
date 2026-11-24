import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useBusiness } from '../hooks/useBusiness';
import { getBusinessId } from '../utils/permissions';
import RoleBadge from './RoleBadge';

export default function BusinessSwitcher({ onNavigate }) {
  const navigate = useNavigate();
  const { businesses, activeBusiness, activeBusinessId, getRoleFor, switchBusiness, loading } =
    useBusiness();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (loading) {
    return <div className="mx-4 mt-4 h-14 animate-pulse rounded-lg bg-slate-100" />;
  }

  if (businesses.length === 0) {
    return (
      <div className="mx-4 mt-4 rounded-lg border border-dashed border-slate-300 p-3 text-center text-xs text-slate-500">
        No businesses yet.{' '}
        <Link
          to="/businesses/new"
          onClick={onNavigate}
          className="font-medium text-indigo-600 hover:text-indigo-700"
        >
          Create one
        </Link>
      </div>
    );
  }

  const handleSelect = (id) => {
    setOpen(false);
    if (id !== activeBusinessId) {
      switchBusiness(id);
      // Business-specific pages remount for the new business; go to a safe page.
      navigate('/');
    }
    onNavigate?.();
  };

  return (
    <div ref={ref} className="relative mx-4 mt-4">
      <p className="mb-1.5 px-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        Active business
      </p>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-left shadow-sm transition hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-slate-900">
            {activeBusiness?.name || 'Select a business'}
          </span>
          {activeBusiness && <RoleBadge role={getRoleFor(activeBusiness)} className="mt-1" />}
        </span>
        <svg className="h-4 w-4 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l4-4 4 4m0 6l-4 4-4-4" />
        </svg>
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute left-0 right-0 z-50 mt-2 max-h-72 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {businesses.map((b) => {
            const id = getBusinessId(b);
            const selected = id === activeBusinessId;
            return (
              <li key={id} role="option" aria-selected={selected}>
                <button
                  type="button"
                  onClick={() => handleSelect(id)}
                  className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-slate-50 ${
                    selected ? 'bg-indigo-50/60' : ''
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-slate-900">{b.name}</span>
                    <RoleBadge role={getRoleFor(b)} className="mt-1" />
                  </span>
                  {selected && (
                    <svg className="h-4 w-4 shrink-0 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
