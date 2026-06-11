import React, { useState, useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';

import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const defaultCenter = [-6.200000, 106.816666]; // Jakarta

function MapEvents({ onLocationSelected }) {
  useMapEvents({
    click(e) {
      onLocationSelected(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

const FitBounds = ({ points }) => {
  const map = useMap();
  useEffect(() => {
    if (points && points.length > 1) {
      map.fitBounds(points, { padding: [40, 40] });
    }
  }, [map, points]);
  return null;
};

const LocationPickerMap = ({
  latitude,
  longitude,
  onLocationChange,
  height = 360,
  origin = null,
  geometry = [],
  tollRoads = [],
}) => {
  const mapHeight = typeof height === 'number' ? `${height}px` : height;
  const markerRef = useRef(null);

  const center = useMemo(() => {
    if (latitude && longitude && !Number.isNaN(parseFloat(latitude)) && !Number.isNaN(parseFloat(longitude))) {
      return [parseFloat(latitude), parseFloat(longitude)];
    }
    return defaultCenter;
  }, [latitude, longitude]);

  const hasLocation = latitude && longitude && !Number.isNaN(parseFloat(latitude)) && !Number.isNaN(parseFloat(longitude));

  const eventHandlers = useMemo(
    () => ({
      dragend() {
        const marker = markerRef.current;
        if (marker != null) {
          const pos = marker.getLatLng();
          onLocationChange(pos.lat, pos.lng);
        }
      },
    }),
    [onLocationChange]
  );

  const fitPoints = useMemo(() => {
    if (geometry && geometry.length > 0) return geometry;
    const pts = [];
    if (origin) pts.push([origin.latitude, origin.longitude]);
    if (hasLocation) pts.push(center);
    return pts;
  }, [geometry, origin, hasLocation, center]);

  const tollRoadList = useMemo(
    () => (tollRoads || []).filter((row) => row?.name),
    [tollRoads]
  );

  return (
    <div style={{ position: 'relative', height: mapHeight, width: '100%' }}>
      <MapContainer center={center} zoom={13} style={{ height: '100%', width: '100%', borderRadius: '8px' }} scrollWheelZoom={true}>
        <TileLayer
          attribution='&copy; Google Maps'
          url="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}"
        />
        {fitPoints.length > 1 && <FitBounds points={fitPoints} />}
        <MapEvents onLocationSelected={onLocationChange} />

        {origin && (
          <Marker position={[origin.latitude, origin.longitude]}>
            <Popup>
              <strong>Gudang:</strong> {origin.name}
            </Popup>
          </Marker>
        )}

        {geometry && geometry.length > 0 && (
          <Polyline positions={geometry} color="#2563eb" weight={4} opacity={0.85} />
        )}

        {tollRoadList.map((road, idx) =>
          road.geometry?.length > 1 ? (
            <Polyline
              key={`${road.name}-${idx}`}
              positions={road.geometry}
              color="#ea580c"
              weight={6}
              opacity={0.9}
            >
              <Tooltip sticky>{road.name}</Tooltip>
            </Polyline>
          ) : null
        )}

        {hasLocation && (
          <Marker
            draggable={true}
            eventHandlers={eventHandlers}
            position={center}
            ref={markerRef}
          >
            <Popup>Geser pin ini ke lokasi yang tepat</Popup>
          </Marker>
        )}
      </MapContainer>

      {tollRoadList.length > 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: '12px',
            left: '12px',
            zIndex: 1000,
            maxWidth: 'min(280px, calc(100% - 24px))',
            background: 'rgba(255,255,255,0.95)',
            padding: '0.65rem 0.75rem',
            borderRadius: '8px',
            fontSize: '0.78rem',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            border: '1px solid rgba(234, 88, 12, 0.25)',
            pointerEvents: 'none',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#9a3412' }}>
            Ruas Tol Dilalui ({tollRoadList.length})
          </div>
          <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
            {tollRoadList.map((road, idx) => (
              <li key={`${road.name}-${idx}`} style={{ color: '#374151' }}>
                {road.name}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div
        style={{
          position: 'absolute',
          top: '10px',
          right: '10px',
          zIndex: 1000,
          background: 'rgba(255,255,255,0.9)',
          padding: '0.5rem',
          borderRadius: '4px',
          fontSize: '0.8rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.35rem',
          alignItems: 'flex-end',
        }}
      >
        <div style={{ pointerEvents: 'none' }}>💡 Klik/geser peta untuk set koordinat</div>
        {hasLocation && (
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: '#2563eb',
              textDecoration: 'none',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
            }}
          >
            Buka di Google Maps ↗
          </a>
        )}
      </div>
    </div>
  );
};

export default LocationPickerMap;
