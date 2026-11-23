"""Фильтрация и сортировка коллекции самолётов."""

from src.aeroplane import Aeroplane


def filter_aeroplanes(planes: list[Aeroplane], countries: list[str]) -> list[Aeroplane]:
    names = {country.strip().casefold() for country in countries if country.strip()}
    return [plane for plane in planes if not names or plane.origin_country.casefold() in names]


def get_aeroplanes_by_altitude(planes: list[Aeroplane], minimum: float, maximum: float) -> list[Aeroplane]:
    minimum = Aeroplane._number(minimum, "Минимальная высота")
    maximum = Aeroplane._number(maximum, "Максимальная высота")
    if minimum is None or maximum is None or minimum > maximum:
        raise ValueError("Некорректный диапазон высот")
    return [plane for plane in planes if plane.altitude is not None and minimum <= plane.altitude <= maximum]


def get_top_aeroplanes(planes: list[Aeroplane], n: int) -> list[Aeroplane]:
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise ValueError("N должно быть положительным целым числом")
    return sorted(
        (plane for plane in planes if plane.altitude is not None), key=lambda plane: plane.altitude, reverse=True
    )[:n]
