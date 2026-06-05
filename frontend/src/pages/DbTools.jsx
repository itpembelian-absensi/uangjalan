import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database, Download, Upload, RefreshCw, CheckCircle, XCircle, Loader, AlertTriangle } from 'lucide-react';

const DbTools = () => {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [backupJob, setBackupJob] = useState(null);
  const [restoreResult, setRestoreResult] = useState(null);
  const [loading, setLoading] = useState({ status: false, backup: false, restore: false });
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

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
    setBackupJob(null);
    try {
      const res = await fetch('/api/db-tools/backup', { method: 'POST', credentials: 'include' });
      const data = await res.json();
      setBackupJob(data);
      pollRef.current = setInterval(async () => {
        try {
          const r = await fetch(`/api/db-tools/backup/${data.backup_id}/status`, { credentials: 'include' });
          const d = await r.json();
          setBackupJob(d);
          if (d.status === 'completed' || d.status === 'failed') {
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
      setBackupJob({ status: 'failed', error: e.message });
      setLoading((l) => ({ ...l, backup: false }));
    }
  };

  const downloadBackup = () => {
    if (backupJob?.download_url) window.open(backupJob.download_url, '_blank');
  };

  const triggerRestore = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) { setError('Pilih file .sql terlebih dahulu.'); return; }
    if (!window.confirm('Database akan dihapus total (skema dan data), lalu diisi ulang dari file backup.\n\nLanjutkan?')) return;

    setLoading((l) => ({ ...l, restore: true }));
    setError(null);
    setRestoreResult(null);

    const fd = new FormData();
    fd.append('file', file);
    fd.append('mode', 'full');
    fd.append('confirm', 'true');

    try {
      const res = await fetch('/api/db-tools/restore', { method: 'POST', credentials: 'include', body: fd });
      const data = await res.json();
      if (res.ok) setRestoreResult({ success: true, ...data });
      else setRestoreResult({ success: false, detail: data.detail || 'Restore gagal' });
    } catch (e) {
      setRestoreResult({ success: false, detail: e.message });
    } finally {
      setLoading((l) => ({ ...l, restore: false }));
    }
  };

  const formatBytes = (b) => {
    if (!b) return '-';
    if (b < 1024) return b + ' B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
    return (b / 1048576).toFixed(2) + ' MB';
  };

  if (!ready) return null;

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <header style={styles.header}>
          <h1 style={styles.title}>Database Tools</h1>
          <p style={styles.subtitle}>Backup dan restore database</p>
        </header>

        {/* Connection */}
        <section style={styles.card}>
          <div style={styles.cardHeader}>
            <div style={styles.statusRow}>
              {loading.status ? (
                <Loader size={16} style={{ animation: 'spin 1s linear infinite' }} />
              ) : status?.connected ? (
                <CheckCircle size={16} color="#059669" />
              ) : (
                <XCircle size={16} color="#dc2626" />
              )}
              <span style={styles.statusText}>
                {loading.status ? 'Memeriksa...' : status?.connected ? 'Terhubung' : 'Tidak terhubung'}
              </span>
              {status?.connected && (
                <span style={styles.statusMeta}>{status.database} @ {status.host}</span>
              )}
            </div>
            <button onClick={checkStatus} style={styles.refreshBtn}>
              <RefreshCw size={14} />
            </button>
          </div>
          {error && (
            <p style={styles.errorText}>{error}</p>
          )}
        </section>

        {/* Actions */}
        <div style={styles.grid}>
          {/* Backup */}
          <section style={styles.card}>
            <div style={styles.sectionHeader}>
              <Download size={18} color="#2563eb" />
              <h2 style={styles.sectionTitle}>Backup</h2>
            </div>
            <p style={styles.sectionDesc}>Export seluruh skema dan data ke file SQL.</p>

            <button onClick={triggerBackup} disabled={loading.backup} style={styles.btnPrimary}>
              {loading.backup ? 'Memproses...' : 'Buat Backup'}
            </button>

            {backupJob && backupJob.status === 'completed' && (
              <div style={styles.resultBox}>
                <div style={styles.resultRow}>
                  <span style={styles.resultLabel}>File</span>
                  <span style={styles.resultValue}>{backupJob.filename}</span>
                </div>
                <div style={styles.resultRow}>
                  <span style={styles.resultLabel}>Ukuran</span>
                  <span style={styles.resultValue}>{formatBytes(backupJob.file_size)}</span>
                </div>
                <button onClick={downloadBackup} style={styles.btnSecondary}>
                  <Download size={14} /> Download
                </button>
              </div>
            )}

            {backupJob && backupJob.status === 'failed' && (
              <p style={styles.errorText}>{backupJob.error}</p>
            )}
          </section>

          {/* Restore */}
          <section style={styles.card}>
            <div style={styles.sectionHeader}>
              <Upload size={18} color="#d97706" />
              <h2 style={styles.sectionTitle}>Restore</h2>
            </div>
            <p style={styles.sectionDesc}>Timpa database dengan file backup SQL.</p>

            <div style={styles.warningBox}>
              <AlertTriangle size={14} />
              <span>Seluruh data dan skema akan dihapus lalu diganti dari file.</span>
            </div>

            <label style={styles.fileLabel}>
              <input type="file" ref={fileInputRef} accept=".sql" style={styles.fileInput} />
            </label>

            <button onClick={triggerRestore} disabled={loading.restore} style={styles.btnDanger}>
              {loading.restore ? 'Memproses...' : 'Mulai Restore'}
            </button>

            {restoreResult && (
              <div style={{ ...styles.resultBox, borderColor: restoreResult.success ? '#d1fae5' : '#fecaca' }}>
                {restoreResult.success ? (
                  <p style={{ color: '#059669', margin: 0, fontSize: '0.85rem' }}>Restore berhasil.</p>
                ) : (
                  <p style={{ color: '#dc2626', margin: 0, fontSize: '0.85rem' }}>{restoreResult.detail}</p>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};

const styles = {
  page: {
    minHeight: '100vh',
    background: '#f8fafc',
    padding: '3rem 1.5rem',
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
    color: '#1e293b',
  },
  container: {
    maxWidth: '720px',
    margin: '0 auto',
  },
  header: {
    marginBottom: '2rem',
  },
  title: {
    fontSize: '1.5rem',
    fontWeight: 600,
    margin: 0,
    color: '#0f172a',
  },
  subtitle: {
    fontSize: '0.875rem',
    color: '#64748b',
    margin: '0.25rem 0 0 0',
  },
  card: {
    background: '#ffffff',
    border: '1px solid #e2e8f0',
    borderRadius: '10px',
    padding: '1.25rem',
    marginBottom: '1rem',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  statusText: {
    fontSize: '0.875rem',
    fontWeight: 500,
  },
  statusMeta: {
    fontSize: '0.8rem',
    color: '#64748b',
    marginLeft: '0.5rem',
  },
  refreshBtn: {
    background: 'none',
    border: '1px solid #e2e8f0',
    borderRadius: '6px',
    padding: '0.4rem',
    cursor: 'pointer',
    color: '#64748b',
    display: 'flex',
    alignItems: 'center',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '1rem',
  },
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    marginBottom: '0.5rem',
  },
  sectionTitle: {
    fontSize: '1rem',
    fontWeight: 600,
    margin: 0,
  },
  sectionDesc: {
    fontSize: '0.8rem',
    color: '#64748b',
    margin: '0 0 1rem 0',
  },
  btnPrimary: {
    width: '100%',
    padding: '0.6rem 1rem',
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontSize: '0.85rem',
    fontWeight: 500,
    cursor: 'pointer',
  },
  btnSecondary: {
    width: '100%',
    padding: '0.5rem 1rem',
    background: '#f1f5f9',
    color: '#1e293b',
    border: '1px solid #e2e8f0',
    borderRadius: '6px',
    fontSize: '0.8rem',
    fontWeight: 500,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.4rem',
    marginTop: '0.75rem',
  },
  btnDanger: {
    width: '100%',
    padding: '0.6rem 1rem',
    background: '#dc2626',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontSize: '0.85rem',
    fontWeight: 500,
    cursor: 'pointer',
  },
  warningBox: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '0.5rem',
    padding: '0.6rem 0.75rem',
    background: '#fffbeb',
    border: '1px solid #fde68a',
    borderRadius: '6px',
    fontSize: '0.75rem',
    color: '#92400e',
    marginBottom: '1rem',
    lineHeight: 1.4,
  },
  fileLabel: {
    display: 'block',
    marginBottom: '1rem',
  },
  fileInput: {
    width: '100%',
    fontSize: '0.8rem',
    padding: '0.5rem',
    border: '1px solid #e2e8f0',
    borderRadius: '6px',
    background: '#f8fafc',
  },
  resultBox: {
    marginTop: '1rem',
    padding: '0.75rem',
    border: '1px solid #e2e8f0',
    borderRadius: '6px',
    background: '#f8fafc',
  },
  resultRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '0.8rem',
    marginBottom: '0.35rem',
  },
  resultLabel: {
    color: '#64748b',
  },
  resultValue: {
    fontWeight: 500,
    color: '#0f172a',
  },
  errorText: {
    fontSize: '0.8rem',
    color: '#dc2626',
    margin: '0.75rem 0 0 0',
  },
};

export default DbTools;
