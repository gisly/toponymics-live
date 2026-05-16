import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { MapIcon } from "lucide-react";
export default function HomePage() {
    const { t } = useTranslation();
    return (_jsxs("div", { className: "max-w-3xl mx-auto px-4 py-12", children: [_jsx("h2", { className: "text-3xl font-semibold mb-4", children: t("site_title") }), _jsx("p", { className: "text-stone-700 mb-8 leading-relaxed", children: "\u0426\u0438\u0444\u0440\u043E\u0432\u0430\u044F \u043F\u043B\u0430\u0442\u0444\u043E\u0440\u043C\u0430 \u0442\u043E\u043F\u043E\u043D\u0438\u043C\u0438\u0447\u0435\u0441\u043A\u0438\u0445 \u0434\u0430\u043D\u043D\u044B\u0445 \u043A\u043E\u0440\u0435\u043D\u043D\u044B\u0445 \u043D\u0430\u0440\u043E\u0434\u043E\u0432 \u0421\u0438\u0431\u0438\u0440\u0438. \u042D\u0442\u043E \u0441\u0442\u0430\u0440\u0442\u043E\u0432\u0430\u044F \u0441\u0442\u0440\u0430\u043D\u0438\u0446\u0430 \u043D\u043E\u0432\u043E\u0433\u043E \u0441\u0430\u0439\u0442\u0430 \u2014 \u043A\u043E\u043D\u0442\u0435\u043D\u0442 \u0431\u0443\u0434\u0435\u0442 \u043D\u0430\u043F\u043E\u043B\u043D\u044F\u0442\u044C\u0441\u044F \u0447\u0435\u0440\u0435\u0437 Wagtail CMS." }), _jsxs(Link, { to: "/map", className: "inline-flex items-center gap-2 px-4 py-2 bg-stone-900 text-white rounded hover:bg-stone-700", children: [_jsx(MapIcon, { size: 18 }), t("nav.map")] })] }));
}
