"""The browser's button (extension/) as the Chrome Web Store and Edge's Add-ons take it: one zip of the folder, without
what only the folder needs (README.md), and without the manifest's key, which gives a copy loaded unpacked the store's
id and which a store does not take. Every file the manifest names is checked to be there; the zip is the same for the
same files (their dates fixed), so that two builds of one version can be compared.

    python3 tools/pack_extension.py [folder]     ->  <folder>/textfold-extension-<version>.zip (default: dist/)
"""
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "extension"
LEAVE = {"README.md"}


def named(m):
    """The files the manifest names."""
    return {m["background"]["service_worker"], m["options_ui"]["page"], *m["icons"].values(),
            *m["action"]["default_icon"].values(), f"_locales/{m['default_locale']}/messages.json"}


def pack(out_dir):
    m = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    m.pop("key", None)
    files = sorted(p for p in SRC.rglob("*") if p.is_file() and not p.name.startswith(".") and p.name not in LEAVE)
    rels = {p.relative_to(SRC).as_posix() for p in files}
    missing = sorted(named(m) - rels)
    if missing:
        raise SystemExit(f"the manifest names what is not there: {', '.join(missing)}")
    out = Path(out_dir) / f"textfold-extension-{m['version']}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel = p.relative_to(SRC).as_posix()
            info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, (json.dumps(m, indent=2, ensure_ascii=False) + "\n").encode("utf-8") if rel == "manifest.json" else p.read_bytes())
    return out, len(files)


if __name__ == "__main__":
    out, n = pack(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dist")
    print(f"{out}  ({n} files, {out.stat().st_size // 1024} KB)")
