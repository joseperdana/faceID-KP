"""Klien HTTP ke Supabase: HTTP/1.1, timeout pendek, dan retry yang tahu diri.

Saat Gibbor, koneksi HTTP/2 bersama milik postgrest-py putus dan setiap
panggilan berikutnya gagal (RemoteProtocolError/LocalProtocolError) atau
menggantung sampai 120 detik. Tes di sini menjaga tiga janji: tidak ada lagi
HTTP/2, tidak ada panggilan yang bisa melewati batas 60 detik nginx, dan retry
tidak pernah menggandakan insert.
"""
from unittest.mock import patch

import httpx
import pytest

import database


def _client(handler):
    return database.build_http_client(transport=httpx.MockTransport(handler))


def _flaky(error, fail_times=1, body=None):
    calls = []

    def handler(request):
        calls.append(request.method)
        if len(calls) <= fail_times:
            raise error("simulasi", request=request)
        return httpx.Response(200, json=body if body is not None else [])

    return handler, calls


URL = "https://contoh.supabase.co/rest/v1/"


def test_supabase_uses_our_http11_client_with_bounded_timeouts():
    assert database.supabase.postgrest.session is database.http_client
    t = database.http_client.timeout
    assert (t.connect, t.read, t.write, t.pool) == (5.0, 10.0, 10.0, 5.0)
    # Retry terburuk untuk satu query tetap jauh di bawah 60 detik nginx.
    assert 2 * (t.connect + t.read) < 60
    pool = database.http_client._transport._pool
    assert pool._http2 is False and pool._http1 is True
    assert pool._max_connections == database.POOL_SIZE >= 40


@pytest.mark.parametrize("error", [
    httpx.RemoteProtocolError, httpx.LocalProtocolError, httpx.ConnectError,
    httpx.ReadTimeout, httpx.ReadError, httpx.PoolTimeout,
])
def test_read_is_retried_once_on_transient_transport_errors(error):
    handler, calls = _flaky(error, body=[{"id": 1}])
    res = _client(handler).get(URL + "users", params={"select": "id"})
    assert res.json() == [{"id": 1}]
    assert calls == ["GET", "GET"]


def test_read_only_rpc_counts_as_read():
    handler, calls = _flaky(httpx.RemoteProtocolError)
    _client(handler).post(URL + "rpc/match_faces", json={"match_count": 1})
    assert calls == ["POST", "POST"]


def test_read_gives_up_after_one_retry_and_reports_to_sentry():
    handler, calls = _flaky(httpx.RemoteProtocolError, fail_times=5)
    with patch("database.capture_error") as captured, pytest.raises(httpx.RemoteProtocolError):
        _client(handler).get(URL + "attendance_logs")
    assert calls == ["GET", "GET"]
    captured.assert_called_once()
    kwargs = captured.call_args.kwargs
    assert kwargs["where"] == "db.retry_exhausted"
    assert kwargs["target"] == "attendance_logs"
    assert kwargs["kind"] == "read"


@pytest.mark.parametrize("error", [httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ReadError])
def test_write_is_not_retried_when_the_server_may_have_received_it(error):
    """insert_user tidak punya penjaga unik: mengulang = anggota kembar."""
    handler, calls = _flaky(error)
    with pytest.raises(error):
        _client(handler).post(URL + "users", json={"full_name": "x"})
    assert calls == ["POST"]


@pytest.mark.parametrize("error", [
    httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout, httpx.LocalProtocolError,
])
def test_write_is_retried_when_request_never_left(error):
    handler, calls = _flaky(error, body=[{"id": 9}])
    res = _client(handler).post(URL + "attendance_logs", json={"user_id": 1})
    assert res.json() == [{"id": 9}]
    assert calls == ["POST", "POST"]


def test_non_transport_errors_pass_through_untouched():
    """Respons 4xx/5xx dari PostgREST (mis. 23505 unique_user_per_day) bukan
    urusan retry — kode kiosk yang menanganinya."""
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(409, json={"code": "23505", "message": "duplicate key"})

    res = _client(handler).post(URL + "attendance_logs", json={"user_id": 1})
    assert res.status_code == 409
    assert calls == [1]
