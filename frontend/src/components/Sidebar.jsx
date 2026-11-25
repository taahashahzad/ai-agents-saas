import { NavLink } from 'react-router-dom';
import { useBusiness } from '../hooks/useBusiness';
import BusinessSwitcher from './BusinessSwitcher';

const ICONS = {
  dashboard:
    'M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z',
  team: 'M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z',
  mail: 'M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75',
  user: 'M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z',
  plus: 'M12 4.5v15m7.5-7.5h-15',
  agents: 'M16 18.5a4 4 0 00-8 0M12 13a3.5 3.5 0 110-7 3.5 3.5 0 010 7zm8 7a4 4 0 00-3-3.87M17 3.4a3.5 3.5 0 010 6.8',
  book: 'M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25',
};

export default function Sidebar({ open, onClose }) {
  const { permissions, pendingInvitationCount } = useBusiness();

  // UX only: hides links the role can't use. The backend enforces access.
  const items = [
    { to: '/', label: 'Dashboard', icon: ICONS.dashboard },
    { to: '/knowledge', label: 'Knowledge Base', icon: ICONS.book },
    permissions.manageAgents && { to: '/agents', label: 'AI Agents', icon: ICONS.agents },
    permissions.viewTeam && { to: '/team', label: 'Team', icon: ICONS.team },
    { to: '/invitations', label: 'Invitations', icon: ICONS.mail, badge: pendingInvitationCount },
    { to: '/profile', label: 'Profile', icon: ICONS.user },
    { to: '/businesses/new', label: 'Create Business', icon: ICONS.plus },
  ].filter(Boolean);

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden" onClick={onClose} />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform lg:static lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center gap-2 border-b border-slate-200 px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            AI
          </div>
          <span className="text-base font-semibold text-slate-900">Agent Platform</span>
        </div>

        <BusinessSwitcher onNavigate={onClose} />

        <nav className="flex-1 space-y-1 overflow-y-auto p-4">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`
              }
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
              </svg>
              <span className="flex-1">{item.label}</span>
              {item.badge > 0 && (
                <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-xs font-semibold text-white">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  );
}
