import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronRight, LogOut } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { MenuIcon } from '../config/menuIcons.jsx';

const STORAGE_SECTIONS = 'sidebar-collapsed-sections';
const STORAGE_GROUPS = 'sidebar-collapsed-groups';

function loadCollapsedSet(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? new Set(parsed) : new Set();
  } catch {
    return new Set();
  }
}

function saveCollapsedSet(key, set) {
  try {
    localStorage.setItem(key, JSON.stringify([...set]));
  } catch {
    /* ignore */
  }
}

/** Sub-menu (icon Minus) digabung ke item induk sebelumnya dalam section yang sama. */
function buildMenuGroups(items) {
  const groups = [];
  let parent = null;
  let children = [];

  const flush = () => {
    if (!parent) return;
    if (children.length > 0) {
      groups.push({ type: 'group', item: parent, children: [...children] });
    } else {
      groups.push({ type: 'link', item: parent });
    }
    parent = null;
    children = [];
  };

  for (const item of items) {
    if (item.icon === 'Minus') {
      if (parent) children.push(item);
      else groups.push({ type: 'link', item });
    } else {
      flush();
      parent = item;
    }
  }
  flush();
  return groups;
}

function pathInSection(items, pathname, menuPaths) {
  return items.some((item) => isNavItemActive(item.path, pathname, menuPaths));
}

/** Hindari parent menu aktif saat halaman sub-menu (mis. /delivery-routes vs /delivery-routes/report). */
function isNavItemActive(itemPath, pathname, menuPaths) {
  if (pathname === itemPath) return true;
  if (itemPath === '/' || !pathname.startsWith(`${itemPath}/`)) return false;
  const hasMoreSpecificMenu = menuPaths.some(
    (p) =>
      p !== itemPath &&
      p.startsWith(`${itemPath}/`) &&
      (pathname === p || pathname.startsWith(`${p}/`)),
  );
  return !hasMoreSpecificMenu;
}

function pathInGroup(group, pathname, menuPaths) {
  if (group.type === 'link') {
    return isNavItemActive(group.item.path, pathname, menuPaths);
  }
  const { item, children } = group;
  if (isNavItemActive(item.path, pathname, menuPaths)) return true;
  return children.some((c) => isNavItemActive(c.path, pathname, menuPaths));
}

const Sidebar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const pathname = location.pathname;

  const [collapsedSections, setCollapsedSections] = useState(() => loadCollapsedSet(STORAGE_SECTIONS));
  const [collapsedGroups, setCollapsedGroups] = useState(() => loadCollapsedSet(STORAGE_GROUPS));

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const menus = user?.menus ?? [];
  const menuPaths = useMemo(() => menus.map((m) => m.path), [menus]);
  const sections = useMemo(() => {
    const acc = {};
    const order = [];
    for (const item of menus) {
      if (!acc[item.section]) {
        acc[item.section] = [];
        order.push(item.section);
      }
      acc[item.section].push(item);
    }
    return order.map((section) => [section, acc[section]]);
  }, [menus]);

  const ensureActiveExpanded = useCallback(() => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      let changed = false;
      for (const [section, items] of sections) {
        if (section === 'Utama') continue;
        if (pathInSection(items, pathname, menuPaths) && next.has(section)) {
          next.delete(section);
          changed = true;
        }
      }
      return changed ? next : prev;
    });

    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      let changed = false;
      for (const [, items] of sections) {
        for (const group of buildMenuGroups(items)) {
          if (group.type !== 'group') continue;
          const id = group.item.id;
          if (pathInGroup(group, pathname, menuPaths) && next.has(id)) {
            next.delete(id);
            changed = true;
          }
        }
      }
      return changed ? next : prev;
    });
  }, [sections, pathname, menuPaths]);

  useEffect(() => {
    ensureActiveExpanded();
  }, [ensureActiveExpanded]);

  useEffect(() => {
    saveCollapsedSet(STORAGE_SECTIONS, collapsedSections);
  }, [collapsedSections]);

  useEffect(() => {
    saveCollapsedSet(STORAGE_GROUPS, collapsedGroups);
  }, [collapsedGroups]);

  const toggleSection = (section) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  };

  const toggleGroup = (id) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const renderNavLink = (item, { sub = false } = {}) => {
    const active = isNavItemActive(item.path, pathname, menuPaths);
    return (
      <Link
        key={item.id}
        to={item.path}
        className={`nav-link ${sub ? 'nav-link-sub' : ''} ${active ? 'active' : ''}`}
      >
        <MenuIcon name={item.icon} size={sub ? 16 : 20} />
        <span style={item.icon === 'Minus' ? { fontSize: '0.9rem' } : undefined}>
          {item.label}
        </span>
      </Link>
    );
  };

  const renderGroup = (group) => {
    if (group.type === 'link') {
      return renderNavLink(group.item);
    }

    const { item, children } = group;
    const isOpen = !collapsedGroups.has(item.id);
    const childActive = children.some((c) => isNavItemActive(c.path, pathname, menuPaths));
    const parentActive = isNavItemActive(item.path, pathname, menuPaths);

    return (
      <div key={item.id} className="nav-group">
        <div className={`nav-group-row ${childActive ? 'nav-group-row-active' : ''}`}>
          <button
            type="button"
            className="nav-group-toggle"
            onClick={() => toggleGroup(item.id)}
            aria-expanded={isOpen}
            aria-label={isOpen ? 'Sembunyikan sub menu' : 'Tampilkan sub menu'}
          >
            {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </button>
          <Link
            to={item.path}
            className={`nav-link nav-link-group ${parentActive ? 'active' : ''}`}
          >
            <MenuIcon name={item.icon} size={20} />
            <span>{item.label}</span>
          </Link>
        </div>
        {isOpen && (
          <div className="sidebar-submenu">
            {children.map((child) => renderNavLink(child, { sub: true }))}
          </div>
        )}
      </div>
    );
  };

  return (
    <aside className="sidebar">
      <div style={{ padding: '0.5rem 1rem' }}>
        <h2
          style={{
            background: 'var(--accent-gradient)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            fontSize: '1.4rem',
          }}
        >
          Biaya Pengiriman
        </h2>
        <p style={{ fontSize: '0.8rem', opacity: 0.7 }}>Premium Logistics</p>
      </div>

      {user && (
        <div className="sidebar-user">
          <div className="sidebar-user-name">{user.full_name}</div>
          <div className="sidebar-user-role">{user.role_label}</div>
        </div>
      )}

      <nav className="sidebar-nav">
        {sections.map(([section, items]) => {
          const groups = buildMenuGroups(items);
          const sectionOpen = section === 'Utama' || !collapsedSections.has(section);

          return (
            <React.Fragment key={section}>
              {section !== 'Utama' && (
                <button
                  type="button"
                  className="sidebar-section sidebar-section-btn"
                  onClick={() => toggleSection(section)}
                  aria-expanded={sectionOpen}
                >
                  <span>{section}</span>
                  {sectionOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
              )}
              {sectionOpen &&
                groups.map((group) =>
                  section === 'Utama' ? renderNavLink(group.item) : renderGroup(group),
                )}
            </React.Fragment>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <button type="button" className="logout-btn" onClick={handleLogout}>
          <LogOut size={18} />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
