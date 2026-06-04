import React, { useState, useEffect } from 'react';
import GlassCard from '../components/GlassCard';
import { Truck, Users, Wallet } from 'lucide-react';

const Dashboard = () => {
  const [stats, setStats] = useState({
    customers: 0,
    drivers: 0,
    vehicles: 0,
    sales: 0,
  });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [custRes, drivRes, vehRes, salesRes] = await Promise.all([
          fetch('/api/customers').then((r) => r.json()),
          fetch('/api/drivers').then((r) => r.json()),
          fetch('/api/vehicles').then((r) => r.json()),
          fetch('/api/sales').then((r) => r.json()),
        ]);

        setStats({
          customers: custRes.length || 0,
          drivers: drivRes.length || 0,
          vehicles: vehRes.length || 0,
          sales: salesRes.length || 0,
        });
      } catch (error) {
        console.error('Failed to fetch stats', error);
      }
    };
    fetchStats();
  }, []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Welcome to UangPengiriman Premium Logistics Panel</p>
        </div>
      </div>

      <div className="grid-cols-4" style={{ marginBottom: '2rem' }}>
        <GlassCard>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Total Customers
              </p>
              <h2 style={{ fontSize: '2.5rem', margin: '0.5rem 0 0 0' }}>{stats.customers}</h2>
            </div>
            <div
              style={{
                padding: '1rem',
                background: 'rgba(59, 130, 246, 0.1)',
                borderRadius: '12px',
                color: '#60a5fa',
              }}
            >
              <Users size={32} />
            </div>
          </div>
        </GlassCard>

        <GlassCard>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Total Drivers
              </p>
              <h2 style={{ fontSize: '2.5rem', margin: '0.5rem 0 0 0' }}>{stats.drivers}</h2>
            </div>
            <div
              style={{
                padding: '1rem',
                background: 'rgba(16, 185, 129, 0.1)',
                borderRadius: '12px',
                color: '#34d399',
              }}
            >
              <Users size={32} />
            </div>
          </div>
        </GlassCard>

        <GlassCard>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Vehicles</p>
              <h2 style={{ fontSize: '2.5rem', margin: '0.5rem 0 0 0' }}>{stats.vehicles}</h2>
            </div>
            <div
              style={{
                padding: '1rem',
                background: 'rgba(245, 158, 11, 0.1)',
                borderRadius: '12px',
                color: '#fbbf24',
              }}
            >
              <Truck size={32} />
            </div>
          </div>
        </GlassCard>

        <GlassCard>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Uang Jalan
              </p>
              <h2 style={{ fontSize: '2.5rem', margin: '0.5rem 0 0 0' }}>{stats.sales}</h2>
            </div>
            <div
              style={{
                padding: '1rem',
                background: 'rgba(139, 92, 246, 0.1)',
                borderRadius: '12px',
                color: '#a78bfa',
              }}
            >
              <Wallet size={32} />
            </div>
          </div>
        </GlassCard>
      </div>

      <GlassCard title="Recent Activity" subtitle="Your logistics overview at a glance.">
        <div
          style={{
            height: '300px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: 0.5,
          }}
        >
          <p>Analytics chart will be rendered here...</p>
        </div>
      </GlassCard>
    </div>
  );
};

export default Dashboard;
