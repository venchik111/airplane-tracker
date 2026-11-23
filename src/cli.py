"""Консольный интерфейс."""

import os

from src.aeroplane import Aeroplane
from src.api import AeroplanesAPI, APIError, BaseAPI
from src.storage import JSONSaver, StorageError
from src.utils import filter_aeroplanes, get_aeroplanes_by_altitude, get_top_aeroplanes


def user_interaction(api: BaseAPI | None = None, saver: JSONSaver | None = None) -> None:
    api = api if api is not None else AeroplanesAPI(os.getenv("OPENSKY_TOKEN"))
    saver = saver if saver is not None else JSONSaver()
    try:
        country = input("Введите страну воздушного пространства: ").strip()
        planes = Aeroplane.cast_to_object_list(api.get_aeroplanes(country))
        saver.replace_all(planes)
        print(f"Получено и сохранено самолётов: {len(planes)}")
        if not planes:
            return
        print("Страны регистрации: " + ", ".join(sorted({p.origin_country for p in planes})))
        while True:
            try:
                n = int(input("Сколько самолётов вывести в топ по высоте? "))
                get_top_aeroplanes([], n)
                break
            except ValueError:
                print("Введите положительное целое число.")
        countries = input("Страны регистрации через запятую (Enter — все): ").split(",")
        selected = filter_aeroplanes(planes, countries)
        while True:
            bounds = input("Диапазон высот в метрах через пробел (Enter — все): ").strip()
            if not bounds:
                break
            try:
                minimum, maximum = map(float, bounds.split())
                selected = get_aeroplanes_by_altitude(selected, minimum, maximum)
                break
            except ValueError:
                print("Введите две конечные высоты: от меньшей к большей.")
        top = get_top_aeroplanes(selected, n)
        print("Позывной | Страна регистрации | Высота | Скорость")
        for plane in top:
            print(plane)
        if not top:
            print("Самолётов с известной высотой по выбранным условиям нет.")
    except (APIError, StorageError, ValueError) as error:
        print(f"Ошибка: {error}")
    except (EOFError, KeyboardInterrupt):
        print("\nРабота завершена.")
