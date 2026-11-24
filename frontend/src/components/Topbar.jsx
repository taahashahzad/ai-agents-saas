import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useBusiness } from '../hooks/useBusiness';
import Button from './Button';
import RoleBadge from './RoleBadge';

export default function Topbar({ onMenuClick }) {
  const { user, profile, logout } = useAuth();
  const { activeBusiness, role, isSystemAdmin } = useBusiness();
  const [loggingOut, setLoggingOut] = useState(false);

  const name = profile?.full_name || profile?.name || user?.displayName || 'User';
  const initial = name.trim().charAt(0).toUpperCase();

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <header className="flex h-16 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 sm:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
        aria-label="Open navigation"
      >
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5M3.75 17.25h16.5" />
        </svg>
      </button>

      <div className="flex min-w-0 flex-1 items-center gap-2">
        {activeBusiness && (
          <>
            <span className="hidden text-xs text-slate-400 sm:inline">Viewing</span>
            <span className="truncate text-sm font-semibold text-slate-900">{activeBusiness.name}</span>
            <RoleBadge role={role} />
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Link to="/profile" className="flex items-center gap-3 rounded-lg hover:opacity-90">
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-slate-900">{name}</p>
            <p className="text-xs text-slate-500">
              {user?.email}
              {isSystemAdmin && <span className="ml-1 font-medium text-rose-600">· System Admin</span>}
            </p>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">
            {initial}
          </div>
        </Link>
        <Button variant="secondary" onClick={handleLogout} loading={loggingOut} className="!py-2">
          Sign out
        </Button>
      </div>
    </header>
  );
}
