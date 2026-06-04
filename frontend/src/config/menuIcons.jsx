import {
  LayoutDashboard,
  Users,
  Car,
  Truck,
  Wallet,
  BarChart3,
  Warehouse as WarehouseIcon,
  Route,
  Fuel,
  MapPinned,
  FileBarChart,
  Shield,
  Table2,
  Minus,
} from 'lucide-react';

export const MENU_ICONS = {
  LayoutDashboard,
  Users,
  Car,
  Truck,
  Wallet,
  BarChart3,
  Warehouse: WarehouseIcon,
  Route,
  Fuel,
  MapPinned,
  FileBarChart,
  Shield,
  Table2,
  Minus,
};

export function MenuIcon({ name, size = 20 }) {
  const Icon = MENU_ICONS[name];
  if (!Icon) return <Minus size={size} style={{ opacity: 0.5 }} />;
  if (name === 'Minus') {
    return (
      <span style={{ width: size, textAlign: 'center', opacity: 0.5, display: 'inline-block' }}>
        -
      </span>
    );
  }
  return <Icon size={size} />;
}
