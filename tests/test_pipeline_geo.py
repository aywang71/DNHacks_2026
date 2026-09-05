import numpy as np

from pipeline import config
from pipeline.geo import cell_id, crosses_dateline, from_local, haversine_km, normalise_lon, to_local


def test_haversine_one_degree_at_equator():
    assert abs(float(haversine_km(0.0, 0.0, 0.0, 1.0)) - 111.19) < 0.01


def test_haversine_is_vectorised_and_symmetric():
    lat1 = np.array([42.749, -6.68]); lon1 = np.array([161.983, -134.66])
    lat2 = np.array([42.795, -6.64]); lon2 = np.array([162.034, -134.79])
    d = haversine_km(lat1, lon1, lat2, lon2)
    assert d.shape == (2,)
    assert np.allclose(d, haversine_km(lat2, lon2, lat1, lon1))
    assert abs(d[0] - 6.60) < 0.05   # showcase shutoff separation


def test_cell_id_showcase_and_dateline_wrap():
    assert int(cell_id(42.749, 161.983)) == 6826   # showcase cell-month prefix 6826-2017-07
    east = int(cell_id(0.0, 179.9)); west = int(cell_id(0.0, -179.9))
    n_lon = 360 // config.CELL_DEG
    assert (east // 100 - west // 100) % n_lon in (1, n_lon - 1)   # adjacent across ±180, not 71 apart
    assert int(cell_id(0.0, 180.0)) == int(cell_id(0.0, -180.0))
    assert int(cell_id(90.0, 0.0)) % 100 == 35                     # lat index clipped into 0..35


def test_local_frame_round_trip_across_dateline():
    lat_c, lon_c = 42.0, 179.5
    lat = np.array([41.5, 42.5, 43.0]); lon = np.array([178.9, -179.6, 179.95])
    x, y = to_local(lat, lon, lat_c, lon_c)
    assert np.all(np.abs(x) < 200)            # unwrapped: no 360-degree jumps
    lat2, lon2 = from_local(x, y, lat_c, lon_c)
    assert np.allclose(lat, lat2, atol=1e-9)
    assert np.allclose(normalise_lon(lon), lon2, atol=1e-9)


def test_crosses_dateline():
    assert crosses_dateline([179.9, -179.9])
    assert not crosses_dateline([161.9, 162.0, 161.4])
    assert not crosses_dateline([])
