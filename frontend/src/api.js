export async function apiFetch(url, options = {}) {
  let res;
  try {
    res = await fetch(url, {
      credentials: 'include',
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        ...(options.headers || {})
      },
      ...options,
    });
  } catch {
    throw new Error(
      'Tidak dapat terhubung ke server. Jalankan npm run dev di folder project, lalu refresh halaman.'
    );
  }
  if (res.status === 401 && url.includes('/api/auth/me')) {
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    let message = `Request gagal (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === 'string') {
        message = data.detail;
        if (res.status === 404 && data.detail === 'Not Found') {
          message = 'API tidak ditemukan. Restart server: npm run dev (di folder project).';
        }
      }
      else if (Array.isArray(data.detail)) {
        message = data.detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
      }
    } catch {
      /* ignore parse errors */
    }
    throw new Error(message);
  }
  if (res.status === 204) return null;
  return res.json();
}
