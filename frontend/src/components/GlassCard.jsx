import React from 'react';

const GlassCard = ({ children, title, subtitle, className = '', style = {} }) => {
  return (
    <div className={`glass-card ${className}`} style={style}>
      {(title || subtitle) && (
        <div style={{ marginBottom: '1.5rem' }}>
          {title && <h3>{title}</h3>}
          {subtitle && <p style={{ fontSize: '0.85rem' }}>{subtitle}</p>}
        </div>
      )}
      {children}
    </div>
  );
};

export default GlassCard;
