import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AppSettingsContext = createContext();

export function useAppSettings() {
  return useContext(AppSettingsContext);
}

export function AppSettingsProvider({ children }) {
  const [settings, setSettings] = useState({
    app_name: 'Biaya Pengiriman',
    app_subtitle: 'Premium Logistics',
    logo_base64: null,
    favicon_base64: null,
    finance_can_unlock_customer: false,
  });

  const [loading, setLoading] = useState(true);

  const fetchSettings = useCallback(async () => {
    try {
      const response = await fetch('/api/app-settings', {
        headers: {
          'Content-Type': 'application/json',
          // Assuming API allows anonymous or we have cookies sent if logged in.
          // In Vite dev server, requests to /api are proxied.
        },
      });
      if (response.ok) {
        const data = await response.json();
        setSettings({
          app_name: data.app_name || 'Biaya Pengiriman',
          app_subtitle: data.app_subtitle || 'Premium Logistics',
          logo_base64: data.logo_base64,
          favicon_base64: data.favicon_base64,
          finance_can_unlock_customer: data.finance_can_unlock_customer || false,
        });
      }
    } catch (error) {
      console.error('Failed to fetch app settings:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  useEffect(() => {
    // Update document title
    document.title = settings.app_name;

    // Update favicon
    let link = document.querySelector("link[rel~='icon']");
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.appendChild(link);
    }
    
    if (settings.favicon_base64) {
      // Detect MIME type roughly, default to image/png
      let mimeType = 'image/png';
      if (settings.favicon_base64.startsWith('data:image/')) {
        link.href = settings.favicon_base64;
      } else {
        if (settings.favicon_base64.startsWith('iVBORw0KGgo')) {
          mimeType = 'image/png';
        } else if (settings.favicon_base64.startsWith('/9j/')) {
          mimeType = 'image/jpeg';
        } else if (settings.favicon_base64.startsWith('AAABAAEA')) {
          mimeType = 'image/x-icon';
        } else if (settings.favicon_base64.startsWith('PHN2Zy')) {
           mimeType = 'image/svg+xml';
        }
        link.href = `data:${mimeType};base64,${settings.favicon_base64}`;
      }
    } else {
      link.href = '/favicon.svg';
      link.type = 'image/svg+xml';
    }
  }, [settings]);

  return (
    <AppSettingsContext.Provider value={{ settings, refreshSettings: fetchSettings, loading }}>
      {children}
    </AppSettingsContext.Provider>
  );
}
