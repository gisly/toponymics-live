import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Routes, Route, NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import HomePage from "./pages/HomePage";
import MapPage from "./pages/MapPage";
export default function App() {
    const { t, i18n } = useTranslation();
    return (_jsxs("div", { className: "min-h-screen flex flex-col bg-stone-50", children: [_jsx("header", { className: "border-b bg-white", children: _jsxs("div", { className: "max-w-7xl mx-auto px-4 py-3 flex items-center justify-between", children: [_jsx("h1", { className: "text-lg font-semibold", children: t("site_title") }), _jsxs("nav", { className: "flex gap-4 text-sm", children: [_jsx(NavLink, { to: "/", className: ({ isActive }) => isActive ? "text-stone-900 font-medium" : "text-stone-600 hover:text-stone-900", children: t("nav.home") }), _jsx(NavLink, { to: "/map", className: ({ isActive }) => isActive ? "text-stone-900 font-medium" : "text-stone-600 hover:text-stone-900", children: t("nav.map") })] }), _jsxs("div", { className: "flex gap-2 text-xs", children: [_jsx("button", { onClick: () => i18n.changeLanguage("ru"), className: i18n.language === "ru" ? "font-semibold" : "text-stone-500", children: "RU" }), _jsx("button", { onClick: () => i18n.changeLanguage("en"), className: i18n.language === "en" ? "font-semibold" : "text-stone-500", children: "EN" })] })] }) }), _jsx("main", { className: "flex-1", children: _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(HomePage, {}) }), _jsx(Route, { path: "/map", element: _jsx(MapPage, {}) })] }) })] }));
}
