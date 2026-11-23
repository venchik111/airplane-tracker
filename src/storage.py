"""Файловое хранилище самолётов."""

import json
from abc import ABC, abstractmethod
from pathlib import Path

from src.aeroplane import Aeroplane


class StorageError(Exception):
    """Ошибка чтения или записи хранилища."""


class BaseSaver(ABC):
    @abstractmethod
    def add_aeroplane(self, aeroplane: Aeroplane) -> None:
        pass

    @abstractmethod
    def get_aeroplanes(self, **criteria) -> list[Aeroplane]:
        pass

    @abstractmethod
    def delete_aeroplane(self, aeroplane: Aeroplane) -> None:
        pass


class JSONSaver(BaseSaver):
    def __init__(self, path: str | Path = "data/aeroplanes.json") -> None:
        self.path = Path(path)

    def get_aeroplanes(self, **criteria) -> list[Aeroplane]:
        allowed = {"callsign", "origin_country", "velocity", "altitude", "icao24", "on_ground"}
        if criteria.keys() - allowed:
            raise ValueError("Неизвестный критерий поиска")
        try:
            if not self.path.exists():
                return []
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("Ожидался список")
            planes = [Aeroplane(**item) for item in data]
        except (OSError, ValueError, TypeError) as error:
            raise StorageError(f"Не удалось прочитать {self.path}: {error}") from error
        return [plane for plane in planes if all(getattr(plane, key) == value for key, value in criteria.items())]

    def _write(self, planes: list[Aeroplane]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps([plane.to_dict() for plane in planes], ensure_ascii=False, indent=2, allow_nan=False),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as error:
            raise StorageError(f"Не удалось сохранить {self.path}: {error}") from error

    @staticmethod
    def _same(left: Aeroplane, right: Aeroplane) -> bool:
        if left.icao24 and right.icao24:
            return left.icao24 == right.icao24
        return left.to_dict() == right.to_dict()

    def add_aeroplane(self, aeroplane: Aeroplane) -> None:
        planes = [plane for plane in self.get_aeroplanes() if not self._same(plane, aeroplane)]
        self._write(planes + [aeroplane])

    def delete_aeroplane(self, aeroplane: Aeroplane) -> None:
        self._write([plane for plane in self.get_aeroplanes() if not self._same(plane, aeroplane)])

    def replace_all(self, planes: list[Aeroplane]) -> None:
        """Заменить снимок целиком, в том числе при пустом ответе API."""
        self._write(planes)
