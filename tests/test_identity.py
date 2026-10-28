"""artcraft_ps5.identity: the fork's title id and data folder become the edition's, and nothing else changes."""

import subprocess
from pathlib import Path, PurePosixPath

import pytest

from artcraft_ps5 import identity
from artcraft_ps5.rebrand import RebrandError

ROOT = PurePosixPath('/data/artcraft')
FILES = {
    'ps5/sce_sys/param.json': '{\n  "conceptId": "99170",\n  "contentId": "UP9000-PPSA99170_00-PS5PROTON0000000",\n'
                              '  "titleId": "PPSA99170"\n}\n',
    'tools/publication-check.py': "OWN = re.compile(rb'PPSA(?!99170|99130|99008)[0-9]{5}')\nTITLE = 'dist/PPSA99170'\n",
    'ps5/CMakeLists.txt': 'set(PROTON_UPDATE_URL "" CACHE STRING "Where the signed release manifest is published")\n',
    'ps5/src/proton_launch.h': '#define PROTON_DATA_ROOT "/data/ps5proton"\n#define SANDBOX "/mnt/sandbox/" "PPSA99170_000"\n',
    'tests/probe.c': 'L"Z:\\\\data\\\\ps5proton\\\\logs";\r\nconst char *x = "metadata/ps5proton /data/ps5proton-old";\r\n',
    'tools/run.py': "PATH = 'Z:\\\\data\\\\ps5proton\\\\run'\nREG = 'Z:\\\\\\\\data\\\\\\\\ps5proton'\n",
    'docs/NOTES.md': 'MihawkOS is PPSA99170 in /data/ps5proton.\n',
    'evidence/run-01.json': '{"title": "PPSA99170", "root": "/data/ps5proton"}\n',
}


@pytest.fixture
def fork(tmp_path):
    for name, text in FILES.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(text.encode())
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'add', '.'], cwd=tmp_path, check=True)
    (tmp_path / 'dist').mkdir()
    (tmp_path / 'dist/built.py').write_text("TITLE = 'PPSA99170'\n")      # a build's output: not the fork's
    return tmp_path


def read(fork: Path, name: str) -> str:
    return (fork / name).read_bytes().decode()


def test_the_title_and_its_folder_become_the_editions(fork):
    changes = identity.identity(fork, 'PPSA99278', ROOT, 'ArtCraft', say=lambda *a: None)
    assert read(fork, 'ps5/sce_sys/param.json') == ('{\n  "conceptId": "99278",\n  "contentId": '
                                                    '"UP9000-PPSA99278_00-ARTCRAFT00000000",\n  "titleId": "PPSA99278"\n}\n')
    assert read(fork, 'tools/publication-check.py') == ("OWN = re.compile(rb'PPSA(?!99278|99170|99130|99008)[0-9]{5}')\n"
                                                        "TITLE = 'dist/PPSA99278'\n")
    assert read(fork, 'ps5/src/proton_launch.h') == ('#define PROTON_DATA_ROOT "/data/artcraft"\n'
                                                     '#define SANDBOX "/mnt/sandbox/" "PPSA99278_000"\n')
    # Every escaping of Z:\data\ps5proton; look-alikes stay; CRLF stays CRLF.
    assert read(fork, 'tests/probe.c') == ('L"Z:\\\\data\\\\artcraft\\\\logs";\r\n'
                                           'const char *x = "metadata/ps5proton /data/ps5proton-old";\r\n')
    assert read(fork, 'tools/run.py') == "PATH = 'Z:\\\\data\\\\artcraft\\\\run'\nREG = 'Z:\\\\\\\\data\\\\\\\\artcraft'\n"
    # Mihawk OS's documents and records, and a build's output, are left as they are.
    for name in ('docs/NOTES.md', 'evidence/run-01.json'):
        assert read(fork, name) == FILES[name]
    assert read(fork, 'dist/built.py') == "TITLE = 'PPSA99170'\n"
    assert changes['ps5/sce_sys/param.json'] == 3 and 'docs/NOTES.md' not in changes


def test_a_label_is_sixteen_characters():
    assert identity.content_id('PPSA99278', 'ArtCraft') == 'UP9000-PPSA99278_00-ARTCRAFT00000000'
    assert len(identity.content_id('PPSA12345', 'A Very Long Brand Name')) == 36


@pytest.mark.parametrize('title_id, root, message', [
    ('PPSA99170', ROOT, 'id of its own'),
    ('ARTCRAFT', ROOT, 'id of its own'),
    ('PPSA99278', PurePosixPath('/data/ps5proton'), 'folder of its own'),
    ('PPSA99278', PurePosixPath('/data/a/b'), 'folder of its own'),
])
def test_mihawk_os_values_are_refused(fork, title_id, root, message):
    with pytest.raises(RebrandError, match=message):
        identity.identity(fork, title_id, root, 'ArtCraft', say=lambda *a: None)
    assert read(fork, 'ps5/sce_sys/param.json') == FILES['ps5/sce_sys/param.json']


def test_a_fork_with_an_update_feed_or_a_moved_string_is_left_alone(fork):
    (fork / 'platform/update').mkdir(parents=True)
    (fork / 'platform/update/release-key.txt').write_text('ab' * 32 + '\n')
    with pytest.raises(RebrandError, match="Mihawk OS's releases"):
        identity.identity(fork, 'PPSA99278', ROOT, 'ArtCraft', say=lambda *a: None)
    (fork / 'platform/update/release-key.txt').unlink()
    (fork / 'ps5/sce_sys/param.json').write_text('{"titleId": "PPSA99170"}\n')
    with pytest.raises(RebrandError, match='param.json: expected 1'):
        identity.identity(fork, 'PPSA99278', ROOT, 'ArtCraft', say=lambda *a: None)
    assert read(fork, 'ps5/src/proton_launch.h') == FILES['ps5/src/proton_launch.h']
