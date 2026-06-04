import React, { useState, useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, useMapEvents } from 'react-leaflet';
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

const LocationPickerMap = ({ latitude, longitude, onLocationChange, height = 360, origin = null, geometry = [] }) => {
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

  return (
    <div style={{ position: 'relative', height: mapHeight, width: '100%' }}>
      <MapContainer center={center} zoom={13} style={{ height: '100%', width: '100%', borderRadius: '8px' }} scrollWheelZoom={true}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
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
      <div style={{
        position: 'absolute',
        top: '10px',
        right: '10px',
        zIndex: 1000,
        background: 'rgba(255,255,255,0.9)',
        padding: '0.5rem',
        borderRadius: '4px',
        fontSize: '0.8rem',
        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
        pointerEvents: 'none'
      }}>
        💡 Klik/geser peta untuk set koordinat
      </div>
    </div>
  );
};

export default LocationPickerMap;
