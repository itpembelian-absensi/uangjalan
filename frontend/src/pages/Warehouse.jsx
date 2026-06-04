import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, Save } from 'lucide-react';
import { apiFetch } from '../api';
import { useCrudWrite } from '../components/CrudWriteAccess';
import LocationPickerMap from '../components/LocationPickerMap';

const Warehouse = () => {
  const canWrite = useCrudWrite();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: 'Gudang Utama',
    address: '',
    city: '',
    latitude: '',
    longitude: '',
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [geocoding, setGeocoding] = useState(false);

  const fetchWarehouse = async () => {
    try {
      const data = await apiFetch('/api/warehouse');
      setForm({
        name: data.name || 'Gudang Utama',
        address: data.address || '',
        city: data.city || '',
        latitude: data.latitude != null ? String(data.latitude) : '',
        longitude: data.longitude != null ? String(data.longitude) : '',
      });
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchWarehouse();
  }, []);

  const handleGeocode = async () => {
    setGeocoding(true);
    setError('');
    try {
      await apiFetch('/api/warehouse', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          address: form.address || null,
          city: form.city || null,
          latitude: form.latitude ? parseFloat(form.latitude) : null,
          longitude: form.longitude ? parseFloat(form.longitude) : null,
        }),
      });
      const data = await apiFetch('/api/warehouse/geocode', { method: 'POST' });
      setForm({
        name: data.name,
        address: data.address || '',
        city: data.city || '',
        latitude: data.latitude != null ? String(data.latitude) : '',
        longitude: data.longitude != null ? String(data.longitude) : '',
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setGeocoding(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await apiFetch('/api/warehouse', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          address: form.address || null,
          city: form.city || null,
          latitude: form.latitude ? parseFloat(form.latitude) : null,
          longitude: form.longitude ? parseFloat(form.longitude) : null,
        }),
      });
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const hasCoords = form.latitude && form.longitude;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Master Gudang</h1>
          <p>Titik koordinat asal pengiriman untuk perhitungan rute, jarak, dan toll</p>
        </div>
      </div>

      {error && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}>
          {error}
        </div>
      )}

      <div className="grid-cols-2" style={{ gap: '1.5rem', alignItems: 'start' }}>
        <div className="glass-panel">
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Nama Gudang</label>
              <input className="form-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required readOnly={!canWrite} />
            </div>
            <div className="form-group">
              <label className="form-label">Alamat</label>
              <textarea className="form-input" rows={3} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} readOnly={!canWrite} />
            </div>
            <div className="form-group">
              <label className="form-label">Kota</label>
              <input className="form-input" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} readOnly={!canWrite} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Latitude</label>
                <input className="form-input" value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} placeholder="-6.200000" readOnly={!canWrite} />
              </div>
              <div className="form-group">
                <label className="form-label">Longitude</label>
                <input className="form-input" value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} placeholder="106.816666" readOnly={!canWrite} />
              </div>
            </div>
            {canWrite && (
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-secondary" onClick={handleGeocode} disabled={geocoding}>
                <MapPin size={16} /> {geocoding ? 'Memproses...' : 'Ambil Koordinat dari Alamat'}
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                <Save size={16} /> {saving ? 'Menyimpan...' : 'Simpan'}
              </button>
            </div>
            )}
          </form>
        </div>

        <div className="glass-panel">
          <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>Peta Gudang</h3>
          <LocationPickerMap
            latitude={form.latitude}
            longitude={form.longitude}
            onLocationChange={
              canWrite
                ? (lat, lng) => setForm({ ...form, latitude: String(lat), longitude: String(lng) })
                : undefined
            }
            height={360}
          />
        </div>
      </div>
    </div>
  );
};

export default Warehouse;
