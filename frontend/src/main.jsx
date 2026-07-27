import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App.jsx'

// Marker commit untuk verifikasi deploy CI (VITE_GIT_SHA diset saat npm run build di server).
window.__BUILD_SHA__ = import.meta.env.VITE_GIT_SHA || 'dev'

// PWA: auto-update service worker saat ada build baru (hanya aktif setelah production build).
registerSW({ immediate: true })

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
