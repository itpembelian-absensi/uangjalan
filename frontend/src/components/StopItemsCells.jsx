import React from 'react';
import { formatItemQuantity, getStopItemLines } from '../utils/deliveryRouteUtils';

export const StopItemsNamesCell = ({ stop }) => {
  const lines = getStopItemLines(stop);
  if (lines.length === 0) return '-';
  return (
    <div className="stop-items-cell">
      {lines.map((line, i) => (
        <div key={`${line.item_name}-${i}`} className="stop-items-cell__line">
          {line.item_name}
        </div>
      ))}
    </div>
  );
};

export const StopItemsQtyCell = ({ stop }) => {
  const lines = getStopItemLines(stop);
  if (lines.length === 0) return '-';
  return (
    <div className="stop-items-cell stop-items-cell--qty">
      {lines.map((line, i) => (
        <div key={`qty-${i}`} className="stop-items-cell__line stop-items-cell__qty">
          {formatItemQuantity(line.quantity)}
        </div>
      ))}
    </div>
  );
};

export default StopItemsNamesCell;
