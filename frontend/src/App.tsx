import { Routes, Route, NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import HomePage from "./pages/HomePage";
import MapPage from "./pages/MapPage";

export default function App() {
  const { t, i18n } = useTranslation();

  return (
    <div className="min-h-screen flex flex-col bg-stone-50">
      <header className="border-b bg-white">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold">{t("site_title")}</h1>
          <nav className="flex gap-4 text-sm">
            <NavLink to="/" className={({ isActive }) =>
              isActive ? "text-stone-900 font-medium" : "text-stone-600 hover:text-stone-900"
            }>
              {t("nav.home")}
            </NavLink>
            <NavLink to="/map" className={({ isActive }) =>
              isActive ? "text-stone-900 font-medium" : "text-stone-600 hover:text-stone-900"
            }>
              {t("nav.map")}
            </NavLink>
          </nav>
          <div className="flex gap-2 text-xs">
            <button
              onClick={() => i18n.changeLanguage("ru")}
              className={i18n.language === "ru" ? "font-semibold" : "text-stone-500"}
            >
              RU
            </button>
            <button
              onClick={() => i18n.changeLanguage("en")}
              className={i18n.language === "en" ? "font-semibold" : "text-stone-500"}
            >
              EN
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/map" element={<MapPage />} />
        </Routes>
      </main>
    </div>
  );
}
