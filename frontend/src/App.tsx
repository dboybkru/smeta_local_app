import { Route, Routes } from "react-router-dom";
import RequireAuth from "./components/RequireAuth";
import AdminUsersPage from "./pages/AdminUsersPage";
import AuthCallbackPage from "./pages/AuthCallbackPage";
import CatalogPage from "./pages/CatalogPage";
import ClientsPage from "./pages/ClientsPage";
import EstimateEditorPage from "./pages/EstimateEditorPage";
import EstimatesListPage from "./pages/EstimatesListPage";
import HomePage from "./pages/HomePage";
import ImportPage from "./pages/ImportPage";
import LoginPage from "./pages/LoginPage";
import PriceLevelsPage from "./pages/PriceLevelsPage";
import ProfilePage from "./pages/ProfilePage";
import AiConfigPage from "./pages/AiConfigPage";
import SuppliersPage from "./pages/SuppliersPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/estimates" element={<EstimatesListPage />} />
        <Route path="/clients" element={<ClientsPage />} />
        <Route path="/estimates/:id" element={<EstimateEditorPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/price-levels" element={<PriceLevelsPage />} />
        <Route path="/admin/suppliers" element={<SuppliersPage />} />
        <Route path="/admin/ai" element={<AiConfigPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Route>
    </Routes>
  );
}
