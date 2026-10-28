"""artcraft_ps5.releases: the checksum lists, the asset names, and downloads checked against their pins."""

import hashlib
import io
import urllib.error

import pytest

from artcraft_ps5 import releases
from artcraft_ps5.edition import EditionError, Pin

SUMS = '''3e634f7e3cc95476c369d59ef0cfed3d1dd6fafd3c351ad81a4ddf3bd792e99d  photocraft-0.16.0-windows-x64-portable.zip
1a073b3ce410cd68bed8c1e5d63f825a8cb578c78106bd54e598d8b07edb6982 *photocraft-0.16.0-windows-x64.msi
c3c52241f9397f80704201f51bfbfe04b02c75acd43164222ed6526d7567b341  photocraft-0.16.0-windows-x86-portable.zip
ecc6e0aee7990538c99dfcccee989066777ec16cb90d6b2c9e5b136e5c60ae92  photocraft-cli-0.16.0-macos-universal.zip
'''


def test_sha256sums_in_text_and_binary_mode():
    sums = releases.parse_sha256sums(SUMS)
    assert sums['photocraft-0.16.0-windows-x64.msi'].startswith('1a073b3c') and len(sums) == 4
    with pytest.raises(EditionError, match='line 1'):
        releases.parse_sha256sums('not a checksum line\n')


def test_the_portable_zip_for_the_arch_and_its_version():
    sums = releases.parse_sha256sums(SUMS)
    assert releases.portable_asset(sums, 'photocraft') == ('photocraft-0.16.0-windows-x64-portable.zip', '0.16.0')
    assert releases.portable_asset(sums, 'photocraft', 'x86')[1] == '0.16.0'
    with pytest.raises(EditionError, match='found 0'):
        releases.portable_asset(sums, 'vectorcraft')
    pre = {'gridcraft-0.13.0-rc.1-windows-x64-portable.zip': 'a' * 64}
    assert releases.portable_asset(pre, 'gridcraft') == ('gridcraft-0.13.0-rc.1-windows-x64-portable.zip', '0.13.0-rc.1')


class FakeResponse(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def serving(data: bytes, honour_ranges: bool = True):
    seen = []

    def opener(request):
        seen.append(dict(request.header_items()))
        span = request.get_header('Range')
        if span and honour_ranges:
            start = int(span.split('=')[1].split('-')[0])
            end = span.split('-')[1]
            body = data[start:int(end) + 1] if end else data[start:]
            return FakeResponse(body, 206, {'Content-Range': f'bytes {start}-{start + len(body) - 1}/{len(data)}'})
        return FakeResponse(data)
    return opener, seen


def pin_for(data: bytes) -> Pin:
    return Pin('photocraft', '0.16.0', 'v0.16.0', 'photocraft-0.16.0-windows-x64-portable.zip',
               'https://example.invalid/p.zip', hashlib.sha256(data).hexdigest(), len(data))


def test_a_download_is_kept_only_when_it_matches_its_pin(tmp_path):
    data = b'zip bytes ' * 1000
    opener, seen = serving(data)
    path = releases.download(pin_for(data), tmp_path, opener, say=lambda *a: None)
    assert path.read_bytes() == data and seen[0].get('User-agent', '').startswith('PS5-ARTCRAFT')
    # Cached and still matching: nothing is asked again.
    assert releases.download(pin_for(data), tmp_path, opener, say=lambda *a: None) == path and len(seen) == 1


def test_a_partial_download_resumes(tmp_path):
    data = bytes(range(256)) * 40
    (tmp_path / 'photocraft-0.16.0-windows-x64-portable.zip.part').write_bytes(data[:3000])
    opener, seen = serving(data)
    path = releases.download(pin_for(data), tmp_path, opener, say=lambda *a: None)
    assert path.read_bytes() == data and seen[0]['Range'] == 'bytes=3000-'


def test_a_server_that_ignores_the_range_starts_over(tmp_path):
    data = b'abcdef' * 500
    (tmp_path / 'photocraft-0.16.0-windows-x64-portable.zip.part').write_bytes(b'garbage')
    opener, _ = serving(data, honour_ranges=False)
    assert releases.download(pin_for(data), tmp_path, opener, say=lambda *a: None).read_bytes() == data


def test_a_wrong_file_is_refused_and_not_kept(tmp_path):
    opener, _ = serving(b'tampered')
    with pytest.raises(EditionError, match='the pin says'):
        releases.download(pin_for(b'original'), tmp_path, opener, say=lambda *a: None)
    assert not list(tmp_path.iterdir())


def test_remote_size_reads_the_byte_range():
    opener, _ = serving(b'x' * 1234)
    assert releases.remote_size('https://example.invalid/a', opener) == 1234

    def no_range(request):
        return FakeResponse(b'x', 200, {})
    with pytest.raises(EditionError, match='no byte range'):
        releases.remote_size('https://example.invalid/a', no_range)
    assert urllib.error  # the real opener's errors surface as they are


def github(releases_by_url: dict[str, str], sizes: dict[str, int]):
    """An opener answering SHA256SUMS.txt by URL and a one-byte range of each asset by URL, as GitHub does."""
    asked = []

    def opener(request):
        url = request.full_url
        asked.append(url)
        if url in releases_by_url:
            return FakeResponse(releases_by_url[url].encode())
        if url in sizes and request.get_header('Range') == 'bytes=0-0':
            return FakeResponse(b'x', 206, {'Content-Range': f'bytes 0-0/{sizes[url]}'})
        raise AssertionError(f'unexpected request: {url}')
    return opener, asked


def test_chosen_versions_are_pinned_and_every_other_pin_is_kept(tmp_path):
    from artcraft_ps5 import edition as editions
    suite = editions.load(need_lock=True)
    repo = suite.launcher.repo
    asset = 'artcraft-launcher-0.7.0-windows-x64-portable.zip'
    url = f'https://github.com/{repo}/releases/download/v0.7.0/{asset}'
    opener, asked = github({f'https://github.com/{repo}/releases/download/v0.7.0/SHA256SUMS.txt': f'{"ab" * 32}  {asset}\n'},
                           {url: 10_000})
    lock = releases.refresh_lock(suite, tmp_path / 'lock.json', opener, versions={'artcraft-launcher': '0.7.0'},
                                 say=lambda *a: None)
    assert lock['pins']['artcraft-launcher'] == {'version': '0.7.0', 'tag': 'v0.7.0', 'asset': asset, 'url': url,
                                                 'sha256': 'ab' * 32, 'size': 10_000}
    assert list(lock['pins']) == list(suite.pins)
    assert all(lock['pins'][app_id]['sha256'] == pin.sha256 for app_id, pin in suite.pins.items() if app_id != 'artcraft-launcher')
    assert len(asked) == 2                     # only the chosen release was read


def test_a_version_must_be_a_release_of_a_suite_app():
    from artcraft_ps5 import edition as editions
    suite = editions.load(need_lock=True)
    with pytest.raises(EditionError, match='not in the suite: nope'):
        releases.refresh_lock(suite, None, versions={'nope': '1.0.0'})
    repo = suite.launcher.repo
    sums = {f'https://github.com/{repo}/releases/download/v0.7.0/SHA256SUMS.txt':
            f'{"ab" * 32}  artcraft-launcher-0.7.1-windows-x64-portable.zip\n'}
    with pytest.raises(EditionError, match='lists artcraft-launcher-0.7.1'):
        releases.release_pin(suite.launcher, 'x64', github(sums, {})[0], '0.7.0')
