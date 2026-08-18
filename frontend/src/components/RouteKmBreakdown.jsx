import React from 'react';
import { formatKm } from '../utils/routeKm';

const formatIDR = (num) =>
  new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(
    Number(num) || 0
  );

const RouteKmBreakdown = ({
  totalKm = 0,
  legs = [],
  variant = 'overlay',
  bbmAmount = null,
  bbmMaster = null,
  bbmSelisih = null,
}) => {
  if (!(totalKm > 0) && legs.length === 0 && bbmAmount == null) return null;

  const isPanel = variant === 'panel';
  const showSelisih = bbmSelisih != null && Number.isFinite(Number(bbmSelisih));
  const selisihNum = Number(bbmSelisih) || 0;
  const selisihLabel = `${selisihNum > 0 ? '+' : ''}${formatIDR(selisihNum)}`;

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
      {bbmAmount != null && (
        <div className="route-km-bbm">
          <span>BBM (km berurutan × 2)</span>
          <span>{formatIDR(bbmAmount)}</span>
        </div>
      )}
      {isPanel && bbmMaster != null && (
        <div className="route-km-bbm-master">
          <span>BBM master (uang jalan)</span>
          <span>{formatIDR(bbmMaster)}</span>
        </div>
      )}
      {showSelisih && (
        <div className={`route-km-bbm-selisih${selisihNum > 0 ? ' is-extra' : selisihNum < 0 ? ' is-save' : ''}`}>
          <span>Selisih BBM</span>
          <span>{selisihLabel}</span>
        </div>
      )}
    </div>
  );
};

export default RouteKmBreakdown;

