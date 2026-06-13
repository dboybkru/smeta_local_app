import { Route, Routes } from "react-router-dom";
import RequireAuth from "./components/RequireAuth";
import AdminUsersPage from "./pages/AdminUsersPage";
import AuthCallbackPage from "./pages/AuthCallbackPage";
import CatalogPage from "./pages/CatalogPage";
import EstimatesListPage from "./pages/EstimatesListPage";
import HomePage from "./pages/HomePage";
import ImportPage from "./pages/ImportPage";
import LoginPage from "./pages/LoginPage";
import PriceLevelsPage from "./pages/PriceLevelsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/estimates" element={<EstimatesListPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/price-levels" element={<PriceLevelsPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
      </Route>
    </Routes>
  );
}
