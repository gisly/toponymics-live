"""
Нормализация FeatureType: name_ru и name_en к нижнему регистру.

Создано после первого импорта данных Мамонтовой — там часть типов попала
с заглавной буквы (Залив, Море, Мыс), часть с маленькой (бор, гора).
Хотим везде с маленькой.

Сгенерируй файл миграции командой:
    docker compose exec django python manage.py makemigrations toponyms --empty --name normalize_feature_type_case

Потом замени содержимое сгенерированного файла на это.
И примени:
    docker compose exec django python manage.py migrate toponyms
"""
from django.db import migrations


def lowercase_feature_types(apps, schema_editor):
    FeatureType = apps.get_model("toponyms", "FeatureType")
    for ft in FeatureType.objects.all():
        changed = False
        if ft.name_ru and ft.name_ru[0].isupper():
            ft.name_ru = ft.name_ru[0].lower() + ft.name_ru[1:]
            changed = True
        if ft.name_en and ft.name_en[0].isupper():
            ft.name_en = ft.name_en[0].lower() + ft.name_en[1:]
            changed = True
        if changed:
            ft.save(update_fields=["name_ru", "name_en"])


def uppercase_feature_types(apps, schema_editor):
    """Реверс — на всякий случай (вряд ли понадобится)."""
    FeatureType = apps.get_model("toponyms", "FeatureType")
    for ft in FeatureType.objects.all():
        changed = False
        if ft.name_ru and ft.name_ru[0].islower():
            ft.name_ru = ft.name_ru[0].upper() + ft.name_ru[1:]
            changed = True
        if ft.name_en and ft.name_en[0].islower():
            ft.name_en = ft.name_en[0].upper() + ft.name_en[1:]
            changed = True
        if changed:
            ft.save(update_fields=["name_ru", "name_en"])


class Migration(migrations.Migration):
    # Поставь сюда имя последней существующей миграции toponyms.
    # Узнать можно: docker compose exec django python manage.py showmigrations toponyms
    dependencies = [
        ("toponyms", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(lowercase_feature_types, uppercase_feature_types),
    ]