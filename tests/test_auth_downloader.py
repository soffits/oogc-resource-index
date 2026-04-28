from __future__ import annotations

import asyncio

import httpx
from typer.testing import CliRunner

import oogc_resource_index.cli as cli
from oogc_resource_index.auth_downloader import AuthVerifyResult, fetch_download_url, parse_download_response
from oogc_resource_index.constants import detail_url


def test_fetch_download_url_posts_raw_colon_endpoint_and_normalizes_relative_down_url() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                text='<input type="hidden" name="formhash" value="abc123">',
                request=request,
            )
        return httpx.Response(200, json={"state": "success", "downUrl": "/downloads/7.zip"}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    result = asyncio.run(
        fetch_download_url(
            detail_url="https://oogc.cc/zy/down-view?fid=7",
            fid="7",
            cookie="session=redacted",
            client=client,
        )
    )
    asyncio.run(client.aclose())

    assert str(requests[1].url) == "https://oogc.cc/plugin.php?id=keke_down:ajax"
    assert requests[1].headers["Referer"] == "https://oogc.cc/zy/down-view?fid=7"
    assert requests[1].content == b"ac=getdown&fid=7&formhash=abc123"
    assert result.down_url == "https://oogc.cc/downloads/7.zip"
    assert result.state == "success"


def test_parse_download_response_normalizes_relative_down_url() -> None:
    state, down_url = parse_download_response('{"state":"ok","downUrl":"files/a.zip"}')

    assert state == "ok"
    assert down_url == "https://oogc.cc/files/a.zip"


def test_detail_url_uses_oogc_hyphen_route() -> None:
    assert detail_url("326") == "https://oogc.cc/zy/down-view-326"


def test_verify_cookie_command_prints_only_safe_diagnostics(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_verify_cookie(**kwargs: object) -> AuthVerifyResult:
        calls.append(kwargs)
        return AuthVerifyResult(status_code=200, state="success", down_url_present=True)

    monkeypatch.setattr(
        cli,
        "verify_cookie",
        fake_verify_cookie,
    )
    runner = CliRunner()

    result = runner.invoke(cli.app, ["verify-cookie", "--cookie", "secret-cookie-value"])

    assert result.exit_code == 0
    assert calls[0]["detail_url"] == "https://oogc.cc/zy/down-view-326"
    assert result.output == "status=200\nstate=success\ndownUrl-present=true\n"
    assert "secret-cookie-value" not in result.output
