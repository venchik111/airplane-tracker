"""Получение границ страны и текущих состояний самолётов."""

from abc import ABC, abstractmethod
from math import isfinite
from time import monotonic, sleep

import requests


class APIError(Exception):
    """Сервис недоступен или вернул неожиданные данные."""


class BaseAPI(ABC):
    @abstractmethod
    def get_aeroplanes(self, country: str) -> dict:
        """Получить состояния самолётов в пределах страны."""


class AeroplanesAPI(BaseAPI):
    def __init__(self, token: str | None = None) -> None:
        self._token = token
        self._cache: dict[str, list[float]] = {}
        self._last_geocode = 0.0

    @staticmethod
    def _get(url: str, **kwargs) -> object:
        try:
            response = requests.get(url, timeout=20, **kwargs)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            raise APIError(f"Не удалось получить данные сервиса: {error}") from error

    def get_coordinates(self, country: str) -> list[float]:
        if not isinstance(country, str) or not country.strip():
            raise ValueError("Введите название страны")
        key = country.strip().casefold()
        if key in self._cache:
            return self._cache[key].copy()
        sleep(max(0, 1.1 - (monotonic() - self._last_geocode)))
        self._last_geocode = monotonic()
        data = self._get(
            "https://nominatim.openstreetmap.org/search",
            params={"country": country.strip(), "format": "json", "limit": 1},
            headers={"User-Agent": "airplane-tracker/0.1 (educational console application)"},
        )
        if data == []:
            raise APIError("Страна не найдена")
        try:
            box = [float(value) for value in data[0]["boundingbox"]]
            if (
                len(box) != 4
                or not all(isfinite(x) for x in box)
                or not -90 <= box[0] <= box[1] <= 90
                or not -180 <= box[2] <= box[3] <= 180
            ):
                raise ValueError
        except (KeyError, TypeError, IndexError, ValueError) as error:
            raise APIError("Некорректные координаты страны") from error
        self._cache[key] = box
        return box.copy()

    def get_aeroplanes(self, country: str) -> dict:
        south, north, west, east = self.get_coordinates(country)
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        data = self._get(
            "https://opensky-network.org/api/states/all",
            params={"lamin": south, "lamax": north, "lomin": west, "lomax": east},
            headers=headers,
        )
        if (
            not isinstance(data, dict)
            or "states" not in data
            or (data["states"] is not None and not isinstance(data["states"], list))
        ):
            raise APIError("Некорректный ответ OpenSky")
        return data
