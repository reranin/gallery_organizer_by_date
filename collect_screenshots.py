import os
import re
import shutil
from pathlib import Path
from typing import Iterable, List, Set, Tuple

from dotenv import load_dotenv


def read_env_values() -> Tuple[Path, Path, List[str], Set[str]]:
    """Read env values and return normalized paths and filters.

    Expected env keys:
      - SOURCE_DIR: directory containing screenshots
      - DEST_DIR: destination directory to collect screenshots
      - SCREENSHOT_NAME_PATTERNS: comma-separated name patterns (substrings)
      - IMAGE_EXTENSIONS: comma-separated extensions without dot
    """
    load_dotenv()

    source_dir_str = os.getenv("SOURCE_DIR", "").strip()
    dest_dir_str = os.getenv("DEST_DIR", "").strip()
    patterns_str = os.getenv(
        "SCREENSHOT_NAME_PATTERNS",
        "Screenshot,Snip,Snipping,Screen Shot,ScreenShot,اسکرین",
    ).strip()
    exts_str = os.getenv("IMAGE_EXTENSIONS", "png,jpg,jpeg,bmp,webp").strip()

    if not source_dir_str:
        raise ValueError("SOURCE_DIR در فایل .env تعریف نشده است.")
    if not dest_dir_str:
        raise ValueError("DEST_DIR در فایل .env تعریف نشده است.")

    source_dir = Path(source_dir_str).expanduser().resolve()
    dest_dir = Path(dest_dir_str).expanduser().resolve()

    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"پوشه منبع وجود ندارد یا پوشه نیست: {source_dir}")

    patterns = [p.strip() for p in patterns_str.split(",") if p.strip()]
    extensions = {e.lower().strip().lstrip('.') for e in exts_str.split(",") if e.strip()}

    return source_dir, dest_dir, patterns, extensions


def is_screenshot_file(path: Path, name_patterns: Iterable[str], allowed_exts: Set[str]) -> bool:
    if not path.is_file():
        return False
    ext = path.suffix.lower().lstrip('.')
    if ext not in allowed_exts:
        return False

    lowercase_name = path.name.lower()
    for pattern in name_patterns:
        if pattern.lower() in lowercase_name:
            return True
    # Regex for common patterns like: "Screen Shot 2025-..."
    if re.search(r"screen\s*shot|screenshot|snip|snipping|اسکرین", lowercase_name):
        return True
    return False


def ensure_directory(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


def move_file(src: Path, dst_dir: Path) -> Path:
    ensure_directory(dst_dir)
    destination = dst_dir / src.name
    counter = 1
    while destination.exists():
        stem, suffix = src.stem, src.suffix
        destination = dst_dir / f"{stem} ({counter}){suffix}"
        counter += 1
    shutil.move(str(src), str(destination))
    return destination


def collect_screenshots() -> int:
    source_dir, dest_dir, patterns, extensions = read_env_values()

    ensure_directory(dest_dir)

    moved_count = 0
    for entry in source_dir.iterdir():
        if is_screenshot_file(entry, patterns, extensions):
            moved_path = move_file(entry, dest_dir)
            moved_count += 1
            print(f"منتقل شد: {entry} -> {moved_path}")

    if moved_count == 0:
        print("فایلی برای انتقال یافت نشد.")
    else:
        print(f"مجموع فایل‌های منتقل‌شده: {moved_count}")
    return moved_count


if __name__ == "__main__":
    try:
        collect_screenshots()
    except Exception as exc:
        print(f"خطا: {exc}")
        raise
