import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function AppHeader() {
  const { user, logout } = useAuth();
  const isSuperuser = !!user?.is_superuser;
  const isOrgAdmin = user?.role === "org_admin";
  const canEdit = user?.role === "estimator" || user?.role === "org_admin" || isSuperuser;
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-stone-200 bg-white px-6 py-3">
      <Link to="/" className="shrink-0 font-serif text-lg text-stone-900">SmetaApp</Link>
      <nav className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <Link to="/catalog" className="text-stone-600 hover:text-stone-900">Каталог</Link>
        <Link to="/estimates" className="text-stone-600 hover:text-stone-900">Сметы</Link>
        {canEdit && (
          <Link to="/clients" className="text-stone-600 hover:text-stone-900">Клиенты</Link>
        )}
        {canEdit && (
          <Link to="/profile" className="text-stone-600 hover:text-stone-900">Реквизиты</Link>
        )}
        {(isOrgAdmin || isSuperuser) && (
          <Link to="/import" className="text-stone-600 hover:text-stone-900">Импорт</Link>
        )}
        {(isOrgAdmin || isSuperuser) && (
          <Link to="/price-levels" className="text-stone-600 hover:text-stone-900">Уровни цен</Link>
        )}
        {(isOrgAdmin || isSuperuser) && (
          <Link to="/admin/suppliers" className="text-stone-600 hover:text-stone-900">Поставщики</Link>
        )}
        {isSuperuser && (
          <Link to="/admin/ai" className="text-stone-600 hover:text-stone-900">AI</Link>
        )}
        {(isOrgAdmin || isSuperuser) && (
          <Link to="/admin/users" className="text-stone-600 hover:text-stone-900">Пользователи</Link>
        )}
        {isSuperuser && (
          <Link to="/admin/orgs" className="text-stone-600 hover:text-stone-900">Организации</Link>
        )}
        {user?.org_name && (
          <span className="text-stone-400 text-xs">[{user.org_name}]</span>
        )}
        <span className="text-stone-400">{user?.email}</span>
        <button onClick={logout} className="text-stone-600 hover:text-stone-900">Выйти</button>
      </nav>
    </header>
  );
}
