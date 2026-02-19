import httpx
import pytest

from app.figma import (
    FigmaAuthError,
    FigmaBadUrlError,
    FigmaClient,
    FigmaNotFoundError,
    extract_file_id,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://www.figma.com/file/AbCdEf1234/My-File", "AbCdEf1234"),
        ("https://figma.com/design/ZyXwVu9876/Flow", "ZyXwVu9876"),
        ("https://figma.com/proto/Qwerty12345/Prototype", "Qwerty12345"),
        ("AbCdEf12345", "AbCdEf12345"),
    ],
)
def test_extract_file_id_success(value: str, expected: str) -> None:
    assert extract_file_id(value) == expected


def test_extract_file_id_failure() -> None:
    with pytest.raises(FigmaBadUrlError):
        extract_file_id("https://example.com/other")


def test_get_file_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/files/AbCdEf1234"
        assert request.headers.get("X-FIGMA-TOKEN") == "token"
        return httpx.Response(200, json={"name": "Demo"})

    transport = httpx.MockTransport(handler)
    client = FigmaClient(transport=transport)

    result = client.get_file("AbCdEf1234", "token")
    assert result["name"] == "Demo"

    client.close()


def test_get_file_auth_error() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(401))
    client = FigmaClient(transport=transport)

    with pytest.raises(FigmaAuthError):
        client.get_file("AbCdEf1234", "token")

    client.close()


def test_get_file_not_found() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    client = FigmaClient(transport=transport)

    with pytest.raises(FigmaNotFoundError):
        client.get_file("AbCdEf1234", "token")

    client.close()
