import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, Link, useNavigate } from 'react-router-dom';
import { Activity, AlertTriangle, BarChart3, Bell, ChevronDown, LayoutDashboard, LogOut, Menu, Server, Settings, User } from 'lucide-react';
import { api } from '../api/client.js';
import useAsync from '../hooks/useAsync.js';
import { useAuth } from '../auth/AuthContext.jsx';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/apis', label: 'Monitored APIs', icon: Server },
  { to: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
];

function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const signOut = async () => {
    setOpen(false);
    await logout();
    navigate('/login');
  };

  return (
    <div className="user-menu" ref={ref}>
      <button type="button" className="user-chip user-btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <User size={16} aria-hidden="true" />
        <span>{user?.username}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && (
        <div className="menu" role="menu">
          <div className="menu-head">
            <strong>{user?.username}</strong>
            <span className="muted small">{user?.email || 'No email set'}</span>
          </div>
          <Link to="/settings" role="menuitem" className="menu-item" onClick={() => setOpen(false)}>
            <User size={16} aria-hidden="true" /> Profile
          </Link>
          <button type="button" role="menuitem" className="menu-item" onClick={signOut}>
            <LogOut size={16} aria-hidden="true" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const { data } = useAsync(() => api.alerts({ is_read: false, page_size: 1 }), [], { refreshMs: 30000 });
  const unread = data?.count || 0;

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className={`sidebar ${open ? 'open' : ''}`} aria-label="Primary">
        <div className="brand">
          <Activity size={22} aria-hidden="true" />
          <span>TrustRoute</span>
        </div>
        <nav>
          <ul>
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink to={to} end={end} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                  <Icon size={18} aria-hidden="true" />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="sidebar-foot">API Monitoring &amp; Reliability</div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />}

      <div className="content">
        <header className="topbar">
          <button type="button" className="icon-btn menu-btn" onClick={() => setOpen((o) => !o)} aria-label="Toggle navigation" aria-expanded={open}>
            <Menu size={20} aria-hidden="true" />
          </button>
          <div className="topbar-right">
            <Link to="/settings#alerts" className="bell" aria-label={`Alerts, ${unread} unread`}>
              <Bell size={18} aria-hidden="true" />
              {unread > 0 && <span className="bell-count">{unread > 99 ? '99+' : unread}</span>}
            </Link>
            <UserMenu />
          </div>
        </header>
        <main id="main" className="main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}