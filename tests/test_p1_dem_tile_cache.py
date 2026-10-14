from contextlib import contextmanager

import pytest

from cutoff.data.dem import _local_tiles
from cutoff.mock import make_mock_run


def test_whole_dem_tile_cache_validates_and_reuses_public_files(tmp_path, monkeypatch):
    root = make_mock_run(tmp_path / "mock")
    content = (root / "dem.tif").read_bytes()
    calls = []

    class Response:
        status_code = 200
        headers = {"Content-Length": str(len(content))}

        def __init__(self, offset=0):
            self.body = content[offset:]
            if offset:
                self.status_code = 206
                self.headers = {"Content-Length": str(len(self.body)),
                                "Content-Range": f"bytes {offset}-{len(content)-1}/{len(content)}"}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield self.body

    @contextmanager
    def get(url, **kwargs):
        calls.append(url)
        byte_range = kwargs.get("headers", {}).get("Range", "bytes=0-")
        offset = int(byte_range.removeprefix("bytes=").removesuffix("-"))
        yield Response(offset)

    monkeypatch.setattr("requests.get", get)
    urls = ["https://copernicus-dem-30m.s3.amazonaws.com/test/test.tif"]
    paths = _local_tiles(urls, tmp_path / "tiles")
    assert paths[0].read_bytes() == content
    assert _local_tiles(urls, tmp_path / "tiles") == paths
    assert calls == urls
    assert not list((tmp_path / "tiles").glob("*.tmp"))

    resumed = tmp_path / "resumed"
    resumed.mkdir()
    (resumed / (paths[0].name + ".123.tmp")).write_bytes(content[:64])
    assert _local_tiles(urls, resumed)[0].read_bytes() == content

    Response.headers = {"Content-Length": str(len(content) + 1)}
    with pytest.raises(RuntimeError, match="Incomplete"):
        _local_tiles(urls, tmp_path / "truncated")
    assert not list((tmp_path / "truncated").iterdir())
