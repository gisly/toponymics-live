"""
Seed-команда для заполнения справочников и демо-топонимов.

Запуск:
    docker compose exec django python manage.py seed_demo
"""
from django.core.management.base import BaseCommand

from apps.toponyms.models import FeatureType, Region, Toponym


REGIONS = [
    {
        "name": "Эвенкия",
        "slug": "evenkia",
        "description": "<p>Эвенкийский муниципальный район Красноярского края</p>",
        "bbox": (90.0, 58.0, 110.0, 70.0),
    },
    {
        "name": "Республика Саха (Якутия)",
        "slug": "sakha",
        "description": "<p>Республика Саха</p>",
        "bbox": (105.0, 55.0, 162.0, 73.0),
    },
]

FEATURE_TYPES = [
    {"code": "river", "name": "Река", "icon": "river", "default_color": "#1d4ed8", "sort_order": 10},
    {"code": "lake", "name": "Озеро", "icon": "lake", "default_color": "#0891b2", "sort_order": 20},
    {"code": "mountain", "name": "Гора/возвышенность", "icon": "mountain", "default_color": "#78716c", "sort_order": 30},
    {"code": "tundra", "name": "Тундра", "icon": "grass", "default_color": "#15803d", "sort_order": 40},
    {"code": "camp", "name": "Стойбище", "icon": "tent", "default_color": "#c2410c", "sort_order": 50},
    {"code": "place", "name": "Урочище", "icon": "marker", "default_color": "#7e22ce", "sort_order": 60},
]

DEMO_TOPONYMS = [
    {
        "name_ru": "Подкаменная Тунгуска",
        "name_evn_cyrillic": "Катанга",
        "feature_type": "river",
        "region": "evenkia",
        "latitude": 61.6,
        "longitude": 100.0,
        "confidence": "high",
    },
    {
        "name_ru": "Нижняя Тунгуска",
        "name_evn_cyrillic": "Катэнга",
        "feature_type": "river",
        "region": "evenkia",
        "latitude": 64.5,
        "longitude": 101.0,
        "confidence": "high",
    },
    {
        "name_ru": "Тура",
        "name_evn_cyrillic": "Турӯ",
        "feature_type": "place",
        "region": "evenkia",
        "latitude": 64.27,
        "longitude": 100.22,
        "confidence": "high",
    },
]


class Command(BaseCommand):
    help = "Заполнить БД демо-данными (регионы, типы объектов, несколько топонимов)"

    def handle(self, *args, **options):
        # Регионы
        regions = {}
        for r in REGIONS:
            obj, created = Region.objects.update_or_create(
                slug=r["slug"],
                defaults={
                    "name": r["name"],
                    "description": r["description"],
                    "bbox_west": r["bbox"][0],
                    "bbox_south": r["bbox"][1],
                    "bbox_east": r["bbox"][2],
                    "bbox_north": r["bbox"][3],
                },
            )
            regions[r["slug"]] = obj
            self.stdout.write(("✓ создан" if created else "  обновлён") + f" регион: {obj.name}")

        # Типы объектов
        feature_types = {}
        for ft in FEATURE_TYPES:
            obj, created = FeatureType.objects.update_or_create(
                code=ft["code"],
                defaults={k: v for k, v in ft.items() if k != "code"},
            )
            feature_types[ft["code"]] = obj
            self.stdout.write(("✓ создан" if created else "  обновлён") + f" тип: {obj.name}")

        # Топонимы
        for t in DEMO_TOPONYMS:
            obj, created = Toponym.objects.update_or_create(
                name_ru=t["name_ru"],
                defaults={
                    "name_evn_cyrillic": t["name_evn_cyrillic"],
                    "feature_type": feature_types[t["feature_type"]],
                    "region": regions[t["region"]],
                    "latitude": t["latitude"],
                    "longitude": t["longitude"],
                    "confidence": t["confidence"],
                },
            )
            self.stdout.write(("✓ создан" if created else "  обновлён") + f" топоним: {obj.name_ru}")

        self.stdout.write(self.style.SUCCESS("Готово."))
