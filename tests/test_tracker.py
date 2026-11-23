import json
from unittest.mock import Mock, patch

import pytest
import requests

from src.aeroplane import Aeroplane
from src.api import AeroplanesAPI, APIError, BaseAPI
from src.cli import user_interaction
from src.storage import BaseSaver, JSONSaver, StorageError
from src.utils import filter_aeroplanes, get_aeroplanes_by_altitude, get_top_aeroplanes


@pytest.fixture
def planes():
    return [
        Aeroplane("LOW ", "United States", 100, 1000, "abc001"),
        Aeroplane("HIGH", "Canada", 200, 3000, "abc002"),
        Aeroplane(None, "Canada", None, None, "abc003"),
    ]


def states():
    return {
        "states": [
            ["abc001", "LOW ", "United States", 1, 1, 0, 0, 1000, False, 100],
            ["abc002", "HIGH", "Canada", 1, 1, 0, 0, 3000, False, 200],
        ]
    }


def test_model(planes):
    low, high, unknown = planes
    assert low.callsign == "LOW"
    assert low < high
    assert low.compare_speed(high) == -1
    assert high.compare_altitude(low) == 1
    assert high.compare_speed(high) == 0
    assert not low.on_ground
    assert "1000 м" in str(low)
    assert "нет данных" in str(unknown)
    assert Aeroplane(**low.to_dict()).to_dict() == low.to_dict()
    assert Aeroplane("X", "Canada", 0, -10).altitude == -10
    with pytest.raises(AttributeError):
        low.altitude = 42
    with pytest.raises(TypeError):
        low < 5
    for other, attr, error in [
        (unknown, "velocity", ValueError),
        (high, "bad", ValueError),
        (5, "altitude", TypeError),
    ]:
        with pytest.raises(error):
            low.compare(other, attr)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"callsign": 5},
        {"origin_country": ""},
        {"origin_country": None},
        {"velocity": -1},
        {"velocity": True},
        {"velocity": "100"},
        {"altitude": float("nan")},
        {"altitude": float("inf")},
        {"icao24": None},
        {"on_ground": 1},
    ],
)
def test_validation(kwargs):
    data = dict(callsign="X", origin_country="Canada", velocity=1, altitude=2)
    data.update(kwargs)
    with pytest.raises(ValueError):
        Aeroplane(**data)


def test_conversion():
    assert len(Aeroplane.cast_to_object_list(states())) == 2
    assert Aeroplane.cast_to_object_list({"states": None}) == []
    for value in ["bad", [[]], [None]]:
        with pytest.raises(ValueError):
            Aeroplane.cast_to_object_list({"states": value})


def test_filters(planes):
    assert filter_aeroplanes(planes, [" united states "]) == [planes[0]]
    assert filter_aeroplanes(planes, []) == planes
    assert filter_aeroplanes(planes, ["Spain"]) == []
    assert get_aeroplanes_by_altitude(planes, 1000, 1000) == [planes[0]]
    assert get_top_aeroplanes(planes, 20) == [planes[1], planes[0]]
    for n in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            get_top_aeroplanes(planes, n)
    for bounds in [(3, 2), (None, 3), (0, float("inf"))]:
        with pytest.raises(ValueError):
            get_aeroplanes_by_altitude(planes, *bounds)


def test_storage(tmp_path, planes):
    saver = JSONSaver(tmp_path / "nested" / "planes.json")
    assert saver.get_aeroplanes() == []
    for plane in planes:
        saver.add_aeroplane(plane)
    saver.add_aeroplane(planes[0])
    assert len(saver.get_aeroplanes()) == 3
    assert len(saver.get_aeroplanes(origin_country="Canada")) == 2
    assert len(saver.get_aeroplanes(altitude=1000)) == 1
    updated = Aeroplane("NEW", "Canada", 150, 4000, "abc001")
    saver.add_aeroplane(updated)
    assert len(saver.get_aeroplanes()) == 3
    assert saver.get_aeroplanes(icao24="abc001")[0].callsign == "NEW"
    saver.delete_aeroplane(updated)
    assert len(saver.get_aeroplanes()) == 2
    saver.replace_all([])
    assert json.loads(saver.path.read_text()) == []
    with pytest.raises(ValueError):
        saver.get_aeroplanes(bad=1)
    anonymous = Aeroplane(None, "Canada", None, None)
    saver.add_aeroplane(anonymous)
    saver.add_aeroplane(anonymous)
    assert len(saver.get_aeroplanes()) == 1
    saver.delete_aeroplane(anonymous)
    assert saver.get_aeroplanes() == []


@pytest.mark.parametrize("content", ["broken", "{}", "[{}]", "[null]"])
def test_corrupt_storage(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content)
    saver = JSONSaver(path)
    with pytest.raises(StorageError):
        saver.get_aeroplanes()
    assert path.read_text() == content


def test_storage_write_error(tmp_path, planes):
    saver = JSONSaver(tmp_path / "bad.json")
    with patch("pathlib.Path.write_text", side_effect=PermissionError("denied")):
        with pytest.raises(StorageError):
            saver.replace_all(planes)


def response(data):
    result = Mock()
    result.json.return_value = data
    return result


@patch("src.api.requests.get")
def test_api(get):
    get.side_effect = [
        response([{"boundingbox": ["10", "20", "30", "40"]}]),
        response(states()),
        response({"states": None}),
    ]
    api = AeroplanesAPI(token="test-token")
    assert len(api.get_aeroplanes("Canada")["states"]) == 2
    assert get.call_args.kwargs["params"] == {"lamin": 10, "lamax": 20, "lomin": 30, "lomax": 40}
    assert get.call_args.kwargs["headers"] == {"Authorization": "Bearer test-token"}
    assert get.call_args.kwargs["timeout"] == 20
    assert api.get_aeroplanes(" canada ") == {"states": None}
    assert get.call_count == 3
    box = api.get_coordinates("Canada")
    box[0] = 99
    assert api.get_coordinates("Canada")[0] == 10


@pytest.mark.parametrize(
    "data",
    [
        [],
        {},
        [{"boundingbox": [1]}],
        [{"boundingbox": ["bad"] * 4}],
        [{"boundingbox": [90, 10, 0, 1]}],
        [{"boundingbox": [0, 1, 0, 999]}],
    ],
)
@patch("src.api.requests.get")
def test_bad_coordinates(get, data):
    get.return_value = response(data)
    with pytest.raises(APIError):
        AeroplanesAPI().get_coordinates("Canada")


def test_empty_country():
    with pytest.raises(ValueError):
        AeroplanesAPI().get_coordinates(" ")


@pytest.mark.parametrize("error", [requests.Timeout("timeout"), requests.HTTPError("429"), ValueError("json")])
@patch("src.api.requests.get")
def test_network_errors(get, error):
    get.side_effect = error
    with pytest.raises(APIError):
        AeroplanesAPI().get_aeroplanes("Canada")


@pytest.mark.parametrize("data", [{}, [], {"states": 3}])
def test_bad_opensky(data):
    with patch.object(AeroplanesAPI, "get_coordinates", return_value=[0, 1, 0, 1]):
        with patch("src.api.requests.get", return_value=response(data)):
            with pytest.raises(APIError):
                AeroplanesAPI().get_aeroplanes("Canada")


def test_abstract_classes():
    for cls in (BaseAPI, BaseSaver):
        with pytest.raises(TypeError):
            cls()


def test_cli(tmp_path, capsys):
    api = Mock(spec=BaseAPI)
    api.get_aeroplanes.return_value = states()
    saver = JSONSaver(tmp_path / "planes.json")
    with patch("builtins.input", side_effect=["Canada", "bad", "0", "2", "Canada", "bad", "4000 1000", "0 5000"]):
        user_interaction(api, saver)
    output = capsys.readouterr().out
    assert "HIGH | Canada" in output
    assert "LOW | United States" not in output
    assert "Введите положительное" in output
    assert len(saver.get_aeroplanes()) == 2


def test_cli_empty_and_errors(tmp_path, capsys):
    api = Mock(spec=BaseAPI)
    saver = JSONSaver(tmp_path / "planes.json")
    api.get_aeroplanes.return_value = {"states": None}
    with patch("builtins.input", return_value="Canada"):
        user_interaction(api, saver)
    assert "самолётов: 0" in capsys.readouterr().out
    api.get_aeroplanes.side_effect = APIError("offline")
    with patch("builtins.input", return_value="Canada"):
        user_interaction(api, saver)
    assert "offline" in capsys.readouterr().out
    with patch("builtins.input", side_effect=EOFError):
        user_interaction(api, saver)
    assert "завершена" in capsys.readouterr().out


def test_cli_no_filter(tmp_path, capsys):
    api = Mock(spec=BaseAPI)
    api.get_aeroplanes.return_value = states()
    with patch("builtins.input", side_effect=["Canada", "1", "", ""]):
        user_interaction(api, JSONSaver(tmp_path / "planes.json"))
    assert "HIGH | Canada" in capsys.readouterr().out
    with patch("builtins.input", side_effect=["Canada", "1", "Spain", ""]):
        user_interaction(api, JSONSaver(tmp_path / "planes.json"))
    assert "по выбранным условиям нет" in capsys.readouterr().out


@pytest.mark.parametrize("data", [[], None, 42, {}, {"wrong_field": []}])
def test_conversion_rejects_invalid_response(data):
    with pytest.raises(ValueError, match="states"):
        Aeroplane.cast_to_object_list(data)


def test_oversized_measurement():
    with pytest.raises(ValueError, match="слишком велико"):
        Aeroplane("X", "Canada", 10**1000, 1)


@pytest.mark.parametrize("box", [[False, True, False, True], [0, 10**1000, 0, 1], "0123"])
def test_invalid_coordinate_types(box):
    with patch.object(AeroplanesAPI, "_get", return_value=[{"boundingbox": box}]):
        with pytest.raises(APIError, match="координаты"):
            AeroplanesAPI().get_coordinates("Canada")


def test_http_status_error():
    result = response({"states": []})
    result.raise_for_status.side_effect = requests.HTTPError("503 Service Unavailable")
    with patch("src.api.requests.get", return_value=result):
        with pytest.raises(APIError, match="503"):
            AeroplanesAPI().get_coordinates("Canada")
    result.json.assert_not_called()


def test_cli_invalid_payload_preserves_snapshot(tmp_path, planes, capsys):
    saver = JSONSaver(tmp_path / "planes.json")
    saver.replace_all(planes)
    previous = saver.path.read_bytes()
    api = Mock(spec=BaseAPI)
    api.get_aeroplanes.return_value = {"wrong_field": []}
    with patch("builtins.input", return_value="Canada"):
        user_interaction(api, saver)
    assert "Ошибка:" in capsys.readouterr().out
    assert saver.path.read_bytes() == previous
