import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { MapIcon } from "lucide-react";

export default function HomePage() {
  const { t } = useTranslation();

  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <h2 className="text-3xl font-semibold mb-4">{t("site_title")}</h2>
      <p className="text-stone-700 mb-8 leading-relaxed">
        Цифровая платформа топонимических данных коренных народов Сибири.
        Это стартовая страница нового сайта — контент будет наполняться через
        Wagtail CMS.
      </p>
      <Link
        to="/map"
        className="inline-flex items-center gap-2 px-4 py-2 bg-stone-900 text-white rounded hover:bg-stone-700"
      >
        <MapIcon size={18} />
        {t("nav.map")}
      </Link>
    </div>
  );
}
