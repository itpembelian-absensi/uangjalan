import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import GlassCard from '../components/GlassCard';
import { Database, Download, Upload, RefreshCw, CheckCircle, XCircle, Loader } from 'lucide-react';

const DbTools = () => {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [backupJob, setBackupJob] = useState(null);
  const [restoreResult, setRestoreResult] = useState(null);
  const [loading, setLoading] = useState({ status: false, backup: false, restore: false });
  const [error, setError] = useState(null);
  const [disabled, setDisabled] = useState(false);
  const [ready, setReady] = useState(false);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

  // Check DB status on mount
  useEffect(() => {
    checkStatus();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const checkStatus = async () => {
    setLoading((l) => ({ ...l, status: true }));
    setError(null);
    try {
      const res = await fetch('/api/db-tools/status', { credentials: 'include' });
      if (res.status === 404) {
        navigate('/', { replace: true });
        return;
      }
      const data = await res.json();
      setStatus(data);
      setDisabled(false);
      setReady(true);
    } catch (e) {
      setError('Tidak dapat terhubung ke server backend.');
      setStatus(null);
      setReady(true);
    } finally {
      setLoading((l) => ({ ...l, status: false }));
    }
  };

  const triggerBackup = async () => {
    setLoading((l) => ({ ...l, backup: true }));
    setError(null);
    setBackupJob(null);
    try {
      const res = await fetch('/api/db-tools/backup', { method: 'POST', credentials: 'include' });
      const data = await res.json();
      setBackupJob(data);

      // Start polling for status
      pollRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/db-tools/backup/${data.backup_id}/status`, { credentials: 'include' });
          const statusData = await statusRes.json();
          setBackupJob(statusData);
          if (statusData.status === 'completed' || statusData.status === 'failed') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setLoading((l) => ({ ...l, backup: false }));
          }
        } catch {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setLoading((l) => ({ ...l, backup: false }));
        }
      }, 1000);
    } catch (e) {
      setError('Backup gagal: ' + e.message);
      setLoading((l) => ({ ...l, backup: false }));
    }
  };

  const downloadBackup = () => {
    if (backupJob && backupJob.download_url) {
      window.open(backupJob.download_url, '_blank');
    }
  };

  const triggerRestore = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError('Pilih file .sql terlebih dahulu');
      return;
    }

    if (!window.confirm('PERINGATAN: Database akan dihapus total (skema dan data), lalu diisi ulang dari file backup. Lanjutkan?')) {
      return;
    }

    setLoading((l) => ({ ...l, restore: true }));
    setError(null);
    setRestoreResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('mode', 'full');
    formData.append('confirm', 'true');

    try {
      const res = await fetch('/api/db-tools/restore', {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setRestoreResult({ success: true, ...data });
      } else {
        setRestoreResult({ success: false, detail: data.detail || 'Restore gagal' });
      }
    } catch (e) {
      setRestoreResult({ success: false, detail: e.message });
    } finally {
      setLoading((l) => ({ ...l, restore: false }));
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes) return '-';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(2) + ' MB';
  };

  if (!ready) return null;

  return (
    <div style={{ minHeight: '100vh', padding: '2rem', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <div className="page-header">
        <div>
          <h1>Database Tools</h1>
          <p>Backup & restore database (dev-only)</p>
        </div>
      </div>

      {error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', padding: '1rem', marginBottom: '1.5rem', color: '#dc2626' }}>
          <XCircle size={16} style={{ display: 'inline', marginRight: '0.5rem', verticalAlign: 'middle' }} />
          {error}
        </div>
      )}

      {/* Status Card */}
      <GlassCard title="Connection Status" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {loading.status ? (
            <Loader size={20} className="spin" />
          ) : status ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {status.connected ? (
                  <CheckCircle size={20} color="#059669" />
                ) : (
                  <XCircle size={20} color="#dc2626" />
                )}
                <span>{status.connected ? 'Connected' : 'Disconnected'}</span>
              </div>
              <span style={{ opacity: 0.6 }}>|</span>
              <span style={{ opacity: 0.7 }}>Database: <strong>{status.database}</strong></span>
              <span style={{ opacity: 0.6 }}>|</span>
              <span style={{ opacity: 0.7 }}>Host: <strong>{status.host}</strong></span>
            </>
          ) : (
            <span style={{ opacity: 0.5 }}>Klik refresh untuk cek koneksi</span>
          )}
          <button onClick={checkStatus} className="btn btn-secondary" style={{ marginLeft: 'auto' }}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </GlassCard>

      <div className="grid-cols-2" style={{ gap: '1.5rem' }}>
        {/* Backup Card */}
        <GlassCard>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <div style={{ padding: '0.75rem', background: 'rgba(59, 130, 246, 0.1)', borderRadius: '10px', color: '#2563eb' }}>
              <Download size={24} />
            </div>
            <div>
              <h3 style={{ margin: 0 }}>Backup Database</h3>
              <p style={{ margin: 0, fontSize: '0.85rem', opacity: 0.7 }}>Export semua data ke file .sql</p>
            </div>
          </div>

          <button
            onClick={triggerBackup}
            disabled={loading.backup}
            className="btn btn-primary"
            style={{ width: '100%', marginBottom: '1rem' }}
          >
            {loading.backup ? <><Loader size={14} className="spin" /> Sedang backup...</> : <><Database size={14} /> Mulai Backup</>}
          </button>

          {backupJob && (
            <div style={{ background: 'rgba(0,0,0,0.03)', borderRadius: '8px', padding: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <span style={{ opacity: 0.7 }}>Status:</span>
                <span style={{
                  color: backupJob.status === 'completed' ? '#059669' :
                         backupJob.status === 'failed' ? '#dc2626' : '#d97706'
                }}>
                  {backupJob.status === 'completed' ? 'Selesai' :
                   backupJob.status === 'failed' ? 'Gagal' : 'Proses...'}
                </span>
              </div>
              {backupJob.file_size && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span style={{ opacity: 0.7 }}>Ukuran:</span>
                  <span>{formatBytes(backupJob.file_size)}</span>
                </div>
              )}
              {backupJob.filename && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <span style={{ opacity: 0.7 }}>File:</span>
                  <span style={{ fontSize: '0.85rem' }}>{backupJob.filename}</span>
                </div>
              )}
              {backupJob.status === 'completed' && (
                <button onClick={downloadBackup} className="btn btn-secondary" style={{ width: '100%' }}>
                  <Download size={14} /> Download File
                </button>
              )}
              {backupJob.error && (
                <p style={{ color: '#f87171', fontSize: '0.85rem', marginTop: '0.5rem' }}>{backupJob.error}</p>
              )}
            </div>
          )}
        </GlassCard>

        {/* Restore Card */}
        <GlassCard>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <div style={{ padding: '0.75rem', background: 'rgba(245, 158, 11, 0.1)', borderRadius: '10px', color: '#d97706' }}>
              <Upload size={24} />
            </div>
            <div>
              <h3 style={{ margin: 0 }}>Restore Database</h3>
              <p style={{ margin: 0, fontSize: '0.85rem', opacity: 0.7 }}>Import data dari file .sql</p>
            </div>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', opacity: 0.8 }}>File SQL:</label>
            <input
              type="file"
              ref={fileInputRef}
              accept=".sql"
              style={{ width: '100%', padding: '0.5rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px', color: 'inherit' }}
            />
          </div>

          <p style={{ fontSize: '0.8rem', color: '#dc2626', marginBottom: '1rem' }}>
            Database akan dihapus total (skema + data) lalu diisi ulang dari file.
          </p>

          <button
            onClick={triggerRestore}
            disabled={loading.restore}
            className="btn btn-primary"
            style={{ width: '100%', background: '#d97706', borderColor: '#b45309', color: '#fff' }}
          >
            {loading.restore ? <><Loader size={14} className="spin" /> Sedang restore...</> : <><Upload size={14} /> Mulai Restore</>}
          </button>

          {restoreResult && (
            <div style={{
              marginTop: '1rem',
              padding: '1rem',
              borderRadius: '8px',
              background: restoreResult.success ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
              border: `1px solid ${restoreResult.success ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            }}>
              {restoreResult.success ? (
                <div style={{ color: '#059669' }}>
                  <CheckCircle size={16} style={{ display: 'inline', marginRight: '0.5rem', verticalAlign: 'middle' }} />
                  {restoreResult.message} (mode: {restoreResult.mode})
                </div>
              ) : (
                <div style={{ color: '#dc2626' }}>
                  <XCircle size={16} style={{ display: 'inline', marginRight: '0.5rem', verticalAlign: 'middle' }} />
                  {restoreResult.detail}
                </div>
              )}
            </div>
          )}
        </GlassCard>
      </div>
      </div>
    </div>
  );
};

export default DbTools;
