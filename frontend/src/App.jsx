import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import ProtectedLayout from './components/ProtectedLayout';
import Layout from './components/Layout';
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
import TollGolongan from './pages/TollGolongan';
import Bbm from './pages/Bbm';
import Users from './pages/Users';
import AccessMatrix from './pages/AccessMatrix';
import DbTools from './pages/DbTools';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
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
              <Route path="toll-golongan" element={<TollGolongan />} />
              <Route path="bbm" element={<Bbm />} />
              <Route path="reports" element={<Reports />} />
              <Route path="users" element={<Users />} />
              <Route path="access-matrix" element={<AccessMatrix />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
