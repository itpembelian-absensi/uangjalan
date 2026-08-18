import React, { useEffect, useMemo, useRef, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { customerMapIcon, warehouseMapIcon } from '../utils/mapIcons';
import { EMPTY_ROUTE_KM, buildRouteKmSummary, formatKm, routePointLabel } from '../utils/routeKm';

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
  const onRouteCalculatedRef = useRef(onRouteCalculated);
  onRouteCalculatedRef.current = onRouteCalculated;
  const pointsRef = useRef(points);
  pointsRef.current = points;
  const pointsKey = coordsKeyFromPoints(points);

  useEffect(() => {
    setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
  }, [points.length, pointsKey]);

  useEffect(() => {
    const currentPoints = pointsRef.current;
    const emit = (summary) => {
      onRouteCalculatedRef.current?.(summary);
    };

    if (currentPoints.length <= 1) {
      setRouteData(null);
      emit(EMPTY_ROUTE_KM);
      return undefined;
    }

    const ac = new AbortController();
    const coords = currentPoints.map((p) => `${p.longitude},${p.latitude}`).join(';');
    fetch(
      `https://router.project-osrm.org/route/v1/driving/${coords}?overview=full&geometries=geojson`,
      { signal: ac.signal }
    )
      .then((res) => res.json())
      .then((data) => {
        if (data.code === 'Ok' && data.routes && data.routes.length > 0) {
          const route = data.routes[0];
          const coordinates = route.geometry.coordinates.map((c) => [c[1], c[0]]);
          const summary = buildRouteKmSummary(currentPoints, route);
          setRouteData({
            geometry: coordinates,
            ...summary,
          });
          emit(summary);
        } else {
          setRouteData(null);
          emit(EMPTY_ROUTE_KM);
        }
      })
      .catch((err) => {
        if (err?.name === 'AbortError') return;
        console.error('OSRM fetch error', err);
        setRouteData(null);
        emit(EMPTY_ROUTE_KM);
      });

    return () => ac.abort();
  }, [pointsKey]);

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
      {points.map((p, idx) => {
        const incomingKm = routeData?.legs?.[idx - 1]?.distanceKm;
        return (
          <Marker
            key={`${p.isWarehouse ? 'wh' : 'c'}-${idx}-${p.latitude}-${p.longitude}`}
            position={[p.latitude, p.longitude]}
            icon={p.isWarehouse ? warehouseMapIcon : customerMapIcon}
            zIndexOffset={p.isWarehouse ? 1000 : idx}
          >
            <Popup>
              <strong>
                {p.isWarehouse ? 'Gudang (titik asal)' : p.label || routePointLabel(p, idx, points)}:
              </strong>{' '}
              {p.name}
              <br />
              <span style={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.85rem' }}>
                {Number(p.latitude).toFixed(6)}, {Number(p.longitude).toFixed(6)}
              </span>
              {incomingKm > 0 && (
                <>
                  <br />
                  <span style={{ fontSize: '0.85rem' }}>
                    Dari {routePointLabel(points[idx - 1], idx - 1, points)}: {formatKm(incomingKm)} km
                  </span>
                </>
              )}
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
};

export default MultiPointMap;
