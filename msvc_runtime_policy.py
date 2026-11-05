"""Versioned public-build policy; never modifies installed runtime libraries."""
import hashlib
from pathlib import Path

MSVC_EXPECTED = {
    "PyQt6/Qt6/bin/MSVCP140.dll": "0f885b509a685d2bbfa652fed26b5fb31d88fbdab0a978c641d1c7b8aa460aa9",
    "PyQt6/Qt6/bin/MSVCP140_1.dll": "bfad5aef4c63a669e3c140655cdfdf395b6c979b400a447bd5dcb65ed8826c3d",
    "PyQt6/Qt6/bin/MSVCP140_2.dll": "3ea06f0ee098b4823cb79599df3780e7f23cce52c19aac31d2a0d47efe33a5e9",
    "PyQt6/Qt6/bin/VCRUNTIME140.dll": "d5e4d9a3e835fa679450145d6a7d94e36573a509317111904d9b3712c30d9066",
    "PyQt6/Qt6/bin/VCRUNTIME140_1.dll": "1f2d41c4aa5db0bc33ebf7b66d72943a817d7ce6cbe880502a9403823633093f",
    "VCRUNTIME140.dll": "4d292623516f65c80482081e62d5dadb759dc16e851de5db24c3cbb57b87db83",
    "VCRUNTIME140_1.dll": "a113f192195f245f17389e6ecbed8005990bcb2476ddad33f7c4c6c86327afe5",
}

def without_bundled_msvc(binaries, expected=None):
    """Fail closed on missing, duplicate, relocated or changed runtime bytes."""
    expected = MSVC_EXPECTED if expected is None else expected
    norm = lambda s: s.replace(chr(92), '/').casefold()
    expected = {norm(k): v for k, v in expected.items()}
    basenames = {n.rsplit('/', 1)[-1] for n in expected}
    found = {}
    for entry in binaries:
        name = norm(entry[0])
        if name.rsplit('/', 1)[-1] in basenames:
            if name not in expected or name in found:
                raise ValueError('MSVC runtime location drift requires review: ' + name)
            found[name] = entry
    if set(found) != set(expected):
        raise ValueError('MSVC runtime member drift requires review')
    for name, entry in found.items():
        if hashlib.sha256(Path(entry[1]).read_bytes()).hexdigest() != expected[name]:
            raise ValueError('MSVC runtime bytes drift requires review: ' + name)
    return [entry for entry in binaries if norm(entry[0]) not in expected]
