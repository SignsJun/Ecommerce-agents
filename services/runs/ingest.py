from pathlib import Path
from zipfile import ZipFile

_MAX = 20 * 1024 * 1024


def extract_olist_zip(src: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with ZipFile(src) as zf:
        for info in zf.infolist():
            if info.is_dir() or info.file_size > _MAX:
                continue
            name = Path(info.filename).name
            if not name.lower().endswith(".csv"):
                continue
            (dest / name).write_bytes(zf.read(info))
    return dest
