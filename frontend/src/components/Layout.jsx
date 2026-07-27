import React, { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Menu, PanelLeft, X } from 'lucide-react';
import Sidebar from './Sidebar';
import { useAppSettings } from '../context/AppSettingsContext';

const STORAGE_SIDEBAR = 'sidebar-hidden';
const MOBILE_BREAKPOINT = 768;

const Layout = () => {
  const location = useLocation();
  const { settings } = useAppSettings();
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < MOBILE_BREAKPOINT);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarHidden, setSidebarHidden] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_SIDEBAR) === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    const onResize = () => {
      const mobile = window.innerWidth < MOBILE_BREAKPOINT;
      setIsMobile(mobile);
      if (!mobile) setMobileMenuOpen(false);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (mobileMenuOpen && isMobile) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileMenuOpen, isMobile]);

  useEffect(() => {
    try {
      if (!isMobile) {
        localStorage.setItem(STORAGE_SIDEBAR, sidebarHidden ? '1' : '0');
      }
    } catch {
      /* ignore */
    }
  }, [sidebarHidden, isMobile]);

  const toggleSidebar = () => {
    if (isMobile) {
      setMobileMenuOpen((prev) => !prev);
    } else {
      setSidebarHidden((prev) => !prev);
    }
  };

  const closeMobileMenu = () => setMobileMenuOpen(false);

  const showDesktopSidebar = !isMobile && !sidebarHidden;
  const showMobileSidebar = isMobile && mobileMenuOpen;

  return (
    <div
      className={`app-layout ${!isMobile && sidebarHidden ? 'sidebar-is-hidden' : ''} ${isMobile ? 'is-mobile' : ''} ${mobileMenuOpen ? 'mobile-menu-open' : ''}`}
    >
      {(showDesktopSidebar || showMobileSidebar) && (
        <>
          {showMobileSidebar && (
            <div className="sidebar-backdrop" onClick={closeMobileMenu} aria-hidden="true" />
          )}
          <Sidebar
            onToggleHide={!isMobile ? toggleSidebar : undefined}
            onMobileClose={isMobile ? closeMobileMenu : undefined}
            isMobile={isMobile}
          />
        </>
      )}
      <main className="main-content">
        {isMobile && (
          <header className="mobile-topbar">
            <button
              type="button"
              className="mobile-menu-btn"
              onClick={toggleSidebar}
              aria-label={mobileMenuOpen ? 'Tutup menu' : 'Buka menu'}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
            <span className="mobile-topbar-title">{settings.app_name || 'Menu'}</span>
          </header>
        )}
        {!isMobile && sidebarHidden && (
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
