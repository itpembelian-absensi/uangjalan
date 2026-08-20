import React from 'react';
import { formatKm } from '../utils/routeKm';

const RouteKmBreakdown = ({
  totalKm = 0,
  legs = [],
  variant = 'overlay',
}) => {
  if (!(totalKm > 0) && legs.length === 0) return null;

  const isPanel = variant === 'panel';

  return (
    <div className={`route-km-breakdown route-km-breakdown-${variant}`}>
      {legs.length > 0 && (
        <ul className="route-km-legs">
          {legs.map((leg, i) => (
            <li key={`${leg.fromLabel}-${leg.toLabel}-${i}`} title={leg.toName || undefined}>
              <span className="route-km-leg-label">
                {leg.fromLabel} → {leg.toLabel}
                {isPanel && leg.toName ? (
                  <span className="route-km-leg-name">{leg.toName}</span>
                ) : null}
              </span>
              <span className="route-km-leg-value">{formatKm(leg.distanceKm)} km</span>
            </li>
          ))}
        </ul>
      )}
      <div className="route-km-total">
        <span>Total jarak tempuh</span>
        <span>{formatKm(totalKm)} km</span>
      </div>
      <div className="route-km-note">Informasi saja. Uang jalan memakai KM terjauh.</div>
    </div>
  );
};

export default RouteKmBreakdown;
