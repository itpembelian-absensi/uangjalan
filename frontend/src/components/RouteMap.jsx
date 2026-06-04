import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, Popup, useMap } from 'react-leaflet';
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

const FitBounds = ({ points }) => {
  const map = useMap();

  useEffect(() => {
    if (points.length > 1) {
      map.fitBounds(points, { padding: [40, 40] });
    } else if (points.length === 1) {
      map.setView(points[0], 13);
    }
  }, [map, points]);

  return null;
};

const RouteMap = ({ origin, destination, geometry, height = 360 }) => {
  const mapHeight = typeof height === 'number' ? `${height}px` : height;
  const center = origin
    ? [origin.latitude, origin.longitude]
    : destination
      ? [destination.latitude, destination.longitude]
      : [-6.2, 106.8];

  const fitPoints =
    geometry?.length > 0
      ? geometry
      : [
          ...(origin ? [[origin.latitude, origin.longitude]] : []),
          ...(destination ? [[destination.latitude, destination.longitude]] : []),
        ];

  useEffect(() => {
    setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
  }, [geometry, origin?.latitude, origin?.longitude, destination?.latitude, destination?.longitude]);

  return (
    <MapContainer
      center={center}
      zoom={11}
      style={{ height: mapHeight, width: '100%', borderRadius: '8px' }}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {fitPoints.length > 0 && <FitBounds points={fitPoints} />}
      {origin && (
        <Marker position={[origin.latitude, origin.longitude]}>
          <Popup>
            <strong>Gudang:</strong> {origin.name}
          </Popup>
        </Marker>
      )}
      {destination && (
        <Marker position={[destination.latitude, destination.longitude]}>
          <Popup>
            <strong>Customer:</strong> {destination.name}
          </Popup>
        </Marker>
      )}
      {geometry?.length > 0 && (
        <Polyline positions={geometry} color="#2563eb" weight={4} opacity={0.85} />
      )}
    </MapContainer>
  );
};

export default RouteMap;
