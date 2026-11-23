"""Модель самолёта и преобразование ответа OpenSky."""

from math import isfinite


class Aeroplane:
    """Неизвестные измерения сохраняются как None, а не как ноль."""

    def __init__(
        self,
        callsign: str | None,
        origin_country: str,
        velocity: float | None,
        altitude: float | None,
        icao24: str = "",
        on_ground: bool = False,
    ) -> None:
        if callsign is not None and not isinstance(callsign, str):
            raise ValueError("Позывной должен быть строкой или None")
        if not isinstance(origin_country, str) or not origin_country.strip():
            raise ValueError("Страна регистрации не должна быть пустой")
        if not isinstance(icao24, str):
            raise ValueError("ICAO24 должен быть строкой")
        if not isinstance(on_ground, bool):
            raise ValueError("Признак нахождения на земле должен быть bool")
        self._callsign = (callsign or "").strip()
        self._origin_country = origin_country.strip()
        self._velocity = self._number(velocity, "Скорость", nonnegative=True)
        self._altitude = self._number(altitude, "Высота")
        self._icao24 = icao24.strip().lower()
        self._on_ground = on_ground

    @staticmethod
    def _number(value: float | None, name: str, nonnegative: bool = False) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError(f"{name}: требуется конечное число или None")
        if nonnegative and value < 0:
            raise ValueError(f"{name} не может быть отрицательной")
        return float(value)

    @property
    def callsign(self) -> str:
        return self._callsign

    @property
    def origin_country(self) -> str:
        return self._origin_country

    @property
    def velocity(self) -> float | None:
        return self._velocity

    @property
    def altitude(self) -> float | None:
        return self._altitude

    @property
    def icao24(self) -> str:
        return self._icao24

    @property
    def on_ground(self) -> bool:
        return self._on_ground

    def compare(self, other: "Aeroplane", attribute: str) -> int:
        """Вернуть -1, 0 или 1; неизвестные измерения сравнить нельзя."""
        if not isinstance(other, Aeroplane):
            raise TypeError("Сравнивать можно только самолёты")
        if attribute not in ("velocity", "altitude"):
            raise ValueError("Сравнение доступно по velocity или altitude")
        left, right = getattr(self, attribute), getattr(other, attribute)
        if left is None or right is None:
            raise ValueError("Измерение отсутствует")
        return (left > right) - (left < right)

    def compare_speed(self, other: "Aeroplane") -> int:
        return self.compare(other, "velocity")

    def compare_altitude(self, other: "Aeroplane") -> int:
        return self.compare(other, "altitude")

    def __lt__(self, other: "Aeroplane") -> bool:
        if not isinstance(other, Aeroplane):
            return NotImplemented
        return self.compare_altitude(other) < 0

    def to_dict(self) -> dict:
        return {
            name: getattr(self, name)
            for name in ("callsign", "origin_country", "velocity", "altitude", "icao24", "on_ground")
        }

    @classmethod
    def cast_to_object_list(cls, data: dict) -> list["Aeroplane"]:
        states = data.get("states")
        if states is None:
            return []
        if not isinstance(states, list):
            raise ValueError("states должен быть списком")
        result = []
        for row in states:
            if not isinstance(row, list) or len(row) < 10:
                raise ValueError("Неполная запись самолёта")
            result.append(cls(row[1], row[2], row[9], row[7], row[0], row[8]))
        return result

    def __str__(self) -> str:
        altitude = "нет данных" if self.altitude is None else f"{self.altitude:.0f} м"
        speed = "нет данных" if self.velocity is None else f"{self.velocity:.1f} м/с"
        return f"{self.callsign or self.icao24 or 'Без позывного'} | {self.origin_country} | {altitude} | {speed}"
