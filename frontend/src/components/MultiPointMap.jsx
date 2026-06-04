import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { customerMapIcon, warehouseMapIcon } from '../utils/mapIcons';

function coordsKeyFromPoints(points) {
  return points.map((p) => `${p.latitude},${p.longitude}`).join('|');
}

const FitBounds = ({ points }) => {
  const map = useMap();
  const coordsKey = useMemo(
    () => points.map((p) => `${p.latitude},${p.longitude}`).join('|'),
    [points],
  );

  useEffect(() => {
    if (points.length > 1) {
      const bounds = L.latLngBounds(points.map((p) => [p.latitude, p.longitude]));
      map.fitBounds(bounds, { padding: [48, 48] });
    } else if (points.length === 1) {
      map.setView([points[0].latitude, points[0].longitude], 13);
    }
  }, [map, coordsKey, points]);

  return null;
};

const MultiPointMap = ({ points, height = 300 }) => {
  const mapHeight = typeof height === 'number' ? `${height}px` : height;
  const center = points.length > 0 ? [points[0].latitude, points[0].longitude] : [-6.2, 106.8];

  useEffect(() => {
    setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
  }, [points.length, coordsKeyFromPoints(points)]);

  return (
    <MapContainer
      center={center}
      zoom={11}
      style={{ height: mapHeight, width: '100%', borderRadius: '8px', zIndex: 1 }}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {points.length > 0 && <FitBounds points={points} />}
      {points.length > 1 && (
        <Polyline
          positions={points.map((p) => [p.latitude, p.longitude])}
          color="#2563eb"
          weight={3}
          opacity={0.7}
          dashArray="8 8"
        />
      )}
      {points.map((p, idx) => (
        <Marker
          key={`${p.isWarehouse ? 'wh' : 'c'}-${idx}-${p.latitude}-${p.longitude}`}
          position={[p.latitude, p.longitude]}
          icon={p.isWarehouse ? warehouseMapIcon : customerMapIcon}
          zIndexOffset={p.isWarehouse ? 1000 : idx}
        >
          <Popup>
            <strong>{p.isWarehouse ? 'Gudang (titik asal)' : p.label || `Customer ${idx}`}:</strong>{' '}
            {p.name}
            <br />
            <span style={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.85rem' }}>
              {Number(p.latitude).toFixed(6)}, {Number(p.longitude).toFixed(6)}
            </span>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
};

export default MultiPointMap;
