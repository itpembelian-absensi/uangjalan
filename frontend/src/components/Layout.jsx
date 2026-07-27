import React, { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { PanelLeft } from 'lucide-react';
import Sidebar from './Sidebar';

const STORAGE_SIDEBAR = 'sidebar-hidden';

const Layout = () => {
  const [sidebarHidden, setSidebarHidden] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_SIDEBAR) === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_SIDEBAR, sidebarHidden ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [sidebarHidden]);

  const toggleSidebar = () => setSidebarHidden((prev) => !prev);

  return (
    <div className={`app-layout ${sidebarHidden ? 'sidebar-is-hidden' : ''}`}>
      {!sidebarHidden && <Sidebar onToggleHide={toggleSidebar} />}
      <main className="main-content">
        {sidebarHidden && (
          <button
            type="button"
            className="sidebar-show-btn"
            onClick={toggleSidebar}
            aria-label="Tampilkan sidebar"
            title="Tampilkan sidebar"
          >
            <PanelLeft size={24} />
          </button>
        )}
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
