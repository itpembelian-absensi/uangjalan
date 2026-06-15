const COORD_PATTERNS = [
  /[?&]q=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/i,
  /[?&]query=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/i,
  /[?&]ll=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/i,
  /[?&]center=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/i,
  /!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/i,
  /@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)(?:,\d+(?:\.\d+)?z)?/i,
  /^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$/,
];

const isValidCoord = (lat, lng) => lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;

export const parseCoordsFromShareText = (text) => {
  const raw = String(text || '').trim();
  if (!raw) return null;

  let decoded = raw;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    decoded = raw;
  }

  for (const pattern of COORD_PATTERNS) {
    const match = decoded.match(pattern);
    if (!match) continue;
    const lat = Number(match[1]);
    const lng = Number(match[2]);
    if (Number.isFinite(lat) && Number.isFinite(lng) && isValidCoord(lat, lng)) {
      return { latitude: lat, longitude: lng };
    }
  }

  return null;
};
