import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { AppSettingsProvider } from './context/AppSettingsContext';
import ProtectedLayout from './components/ProtectedLayout';
import Layout from './components/Layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Customers from './pages/Customers';
import Drivers from './pages/Drivers';
import Vehicles from './pages/Vehicles';
import VehicleBrands from './pages/VehicleBrands';
import VehicleTypes from './pages/VehicleTypes';
import Reports from './pages/Reports';
import Sales from './pages/Sales';
import DeliveryRoutesList from './pages/DeliveryRoutesList';
import DeliveryRoutesReport from './pages/DeliveryRoutesReport';
import DeliveryRouteForm from './pages/DeliveryRouteForm';
import Warehouse from './pages/Warehouse';
import TollSections from './pages/TollSections';
import TollSectionForm from './pages/TollSectionForm';
import TollGolongan from './pages/TollGolongan';
import TollGates from './pages/TollGates';
import Bbm from './pages/Bbm';
import UangMel from './pages/UangMel';
import UangPelabuhan from './pages/UangPelabuhan';
import RouteFeeMaster from './pages/RouteFeeMaster';
import { ROUTE_FEE_DEFS } from './utils/routeFeeConfig';
import Users from './pages/Users';
import AccessMatrix from './pages/AccessMatrix';
import DbTools from './pages/DbTools';
import AppSettings from './pages/AppSettings';

function App() {
  return (
    <BrowserRouter>
      <AppSettingsProvider>
        <AuthProvider>
        <ErrorBoundary>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/db-tools" element={<DbTools />} />
            <Route element={<ProtectedLayout />}>
              <Route path="/" element={<Layout />}>
                <Route index element={<Dashboard />} />
                <Route path="customers" element={<Customers />} />
                <Route path="drivers" element={<Drivers />} />
                <Route path="vehicles" element={<Vehicles />} />
                <Route path="vehicle-brands" element={<VehicleBrands />} />
                <Route path="vehicle-types" element={<VehicleTypes />} />
                <Route path="delivery-routes" element={<DeliveryRoutesList />} />
                <Route path="delivery-routes/report" element={<DeliveryRoutesReport />} />
                <Route path="delivery-routes/new" element={<DeliveryRouteForm />} />
                <Route path="delivery-routes/:routeId/edit" element={<DeliveryRouteForm />} />
                <Route path="sales" element={<Sales />} />
                <Route path="warehouse" element={<Warehouse />} />
                <Route path="toll-sections" element={<TollSections />} />
                <Route path="toll-sections/new" element={<TollSectionForm />} />
                <Route path="toll-sections/:id/edit" element={<TollSectionForm />} />
                <Route path="toll-golongan" element={<TollGolongan />} />
                <Route path="toll-gates" element={<TollGates />} />
                <Route path="bbm" element={<Bbm />} />
                <Route path="uang-mel" element={<UangMel />} />
                <Route path="uang-pelabuhan" element={<UangPelabuhan />} />
                {ROUTE_FEE_DEFS.map((fee) => (
                  <Route
                    key={fee.path}
                    path={fee.path.replace(/^\//, '')}
                    element={
                      <RouteFeeMaster
                        feeType={fee.apiPath}
                        title={fee.title}
                        amountLabel={`Nominal ${fee.label} (Rp)`}
                      />
                    }
                  />
                ))}
                <Route path="reports" element={<Reports />} />
                <Route path="users" element={<Users />} />
                <Route path="access-matrix" element={<AccessMatrix />} />
                <Route path="app-settings" element={<AppSettings />} />
              </Route>
            </Route>
          </Routes>
        </ErrorBoundary>
        </AuthProvider>
      </AppSettingsProvider>
    </BrowserRouter>
  );
}

export default App;
