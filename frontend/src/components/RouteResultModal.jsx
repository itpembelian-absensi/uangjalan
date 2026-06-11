import React from 'react';
import { X, MapPin } from 'lucide-react';
import RouteMap from './RouteMap';
import TollEstimateTable from './TollEstimateTable';
import RouteTollGateInfo from './RouteTollGateInfo';

const RouteResultModal = ({ result, onClose, onApplyToll }) => {
  if (!result) return null;

  return (
    <div className="modal-overlay" style={{ zIndex: 1100 }}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '820px', width: '95%' }}
      >
        <div className="modal-header">
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
            <MapPin size={20} /> Rute Gudang → {result.customer_name}
          </h2>
          <button type="button" className="btn-icon" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <div className="modal-body">
          <RouteMap
            origin={result.origin}
            destination={result.destination}
            geometry={result.geometry}
          />

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '1rem',
              marginTop: '1.25rem',
            }}
          >
            <div className="glass-card" style={{ padding: '1rem', boxShadow: 'none' }}>
              <p className="form-label" style={{ marginBottom: '0.35rem' }}>Jarak</p>
              <p style={{ margin: 0, fontSize: '1.35rem', fontWeight: 700 }}>
                {result.distance_km.toLocaleString('id-ID')} km
              </p>
            </div>
            <div className="glass-card" style={{ padding: '1rem', boxShadow: 'none' }}>
              <p className="form-label" style={{ marginBottom: '0.35rem' }}>Estimasi Waktu</p>
              <p style={{ margin: 0, fontSize: '1.35rem', fontWeight: 700 }}>
                {result.duration_min.toLocaleString('id-ID')} menit
              </p>
            </div>
          </div>

          <div style={{ marginTop: '1rem' }}>
            <RouteTollGateInfo
              segments={result.toll_breakdown}
              tollSource={result.toll_source}
              tollNote={result.toll_note}
            />
            <TollEstimateTable
              items={result.toll_by_vehicle}
              isEstimate={result.toll_is_estimate}
            />
          </div>

          {result.toll_note && !result.toll_breakdown?.length && (
            <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {result.toll_note}
            </p>
          )}

          <div style={{ marginTop: '1rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            <div><strong>Dari:</strong> {result.origin.name} ({result.origin.latitude.toFixed(5)}, {result.origin.longitude.toFixed(5)})</div>
            <div><strong>Ke:</strong> {result.destination.name} ({result.destination.latitude.toFixed(5)}, {result.destination.longitude.toFixed(5)})</div>
          </div>
        </div>
        <div className="modal-footer">
          {onApplyToll && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onApplyToll(Math.round(result.toll_idr))}
            >
              Isi Uang Jalan Tambahan = Toll
            </button>
          )}
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
};

export default RouteResultModal;
