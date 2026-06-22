import React, { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { customerMapIcon, warehouseMapIcon } from '../utils/mapIcons';

function coordsKeyFromPoints(points) {
  return points.map((p) => `${p.latitude},${p.longitude}`).join('|');
}

const FitBounds = ({ points, routeGeometry }) => {
  const map = useMap();
  const coordsKey = useMemo(
    () => points.map((p) => `${p.latitude},${p.longitude}`).join('|'),
    [points],
  );

  useEffect(() => {
    if (routeGeometry && routeGeometry.length > 1) {
      const bounds = L.latLngBounds(routeGeometry);
      map.fitBounds(bounds, { padding: [48, 48] });
    } else if (points.length > 1) {
      const bounds = L.latLngBounds(points.map((p) => [p.latitude, p.longitude]));
      map.fitBounds(bounds, { padding: [48, 48] });
    } else if (points.length === 1) {
      map.setView([points[0].latitude, points[0].longitude], 13);
    }
  }, [map, coordsKey, points, routeGeometry]);

  return null;
};

const MultiPointMap = ({ points, height = 300, onRouteCalculated }) => {
  const mapHeight = typeof height === 'number' ? `${height}px` : height;
  const center = points.length > 0 ? [points[0].latitude, points[0].longitude] : [-6.2, 106.8];
  const [routeData, setRouteData] = useState(null);

  useEffect(() => {
    setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
  }, [points.length, coordsKeyFromPoints(points)]);

  useEffect(() => {
    if (points.length > 1) {
      const coords = points.map((p) => `${p.longitude},${p.latitude}`).join(';');
      fetch(`https://router.project-osrm.org/route/v1/driving/${coords}?overview=full&geometries=geojson`)
        .then((res) => res.json())
        .then((data) => {
          if (data.code === 'Ok' && data.routes && data.routes.length > 0) {
            const route = data.routes[0];
            const coordinates = route.geometry.coordinates.map((c) => [c[1], c[0]]);
            setRouteData({
              geometry: coordinates,
              distanceKm: route.distance / 1000,
            });
            if (onRouteCalculated) {
              onRouteCalculated(route.distance / 1000);
            }
          } else {
            setRouteData(null);
            if (onRouteCalculated) onRouteCalculated(0);
          }
        })
        .catch((err) => {
          console.error("OSRM fetch error", err);
          setRouteData(null);
          if (onRouteCalculated) onRouteCalculated(0);
        });
    } else {
      setRouteData(null);
      if (onRouteCalculated) onRouteCalculated(0);
    }
  }, [points.length, coordsKeyFromPoints(points), onRouteCalculated]);

  return (
    <MapContainer
      center={center}
      zoom={11}
      style={{ height: mapHeight, width: '100%', borderRadius: '8px', zIndex: 1 }}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; Google Maps'
        url="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}"
      />
      {points.length > 0 && <FitBounds points={points} routeGeometry={routeData?.geometry} />}
      {routeData?.geometry ? (
        <Polyline
          positions={routeData.geometry}
          color="#2563eb"
          weight={4}
          opacity={0.85}
        />
      ) : points.length > 1 && (
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
            {p.distance_km && (
              <>
                <br />
                <span style={{ fontSize: '0.85rem' }}>Jarak: {p.distance_km} km</span>
              </>
            )}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
};

export default MultiPointMap;
