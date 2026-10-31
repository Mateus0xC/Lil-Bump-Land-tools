"""Builds release zips into the output folder. Paths and names come from config.json.

output/data/       every folder in datapacks_dir, zipped (existing .zip files are copied as-is)
output/resources/  merged_resourcepack: its sources from resourcepacks_dir merged into one zip

- Folder contents go at the root of the zip (no wrapping folder).
- Anything listed in "exclude" (e.g. .git, spyglass.json) is left out.
"""

import json
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if not (HERE / "config.json").exists():
    raise SystemExit("config.json not found: copy config.example.json to config.json and set your paths.")
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

# Relative paths in config.json are relative to this script's folder
SOURCE = (HERE / CONFIG["datapacks_dir"]).resolve()
RESOURCEPACKS = (HERE / CONFIG["resourcepacks_dir"]).resolve()
OUTPUT = (HERE / CONFIG["output_dir"]).resolve()
EXCLUDE = set(CONFIG["exclude"])

MERGED_NAME = CONFIG["merged_resourcepack"]["name"]
MERGED_SOURCES = CONFIG["merged_resourcepack"]["sources"]
MERGED_DESCRIPTION = CONFIG["merged_resourcepack"]["description"]


def iter_files(folder: Path):
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder)
        if EXCLUDE.intersection(rel.parts) or not path.is_file():
            continue
        yield rel.as_posix(), path


def zip_folder(folder: Path, dest: Path) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, path in iter_files(folder):
            zf.write(path, rel)


def merge_dicts(dict1, dict2):
    for k, v in dict2.items():
        if isinstance(v, dict) and isinstance(dict1.get(k), dict):
            merge_dicts(dict1[k], v)
        elif isinstance(v, list) and isinstance(dict1.get(k), list):
            # For lists (e.g. overrides), append only the new items
            dict1[k].extend(x for x in v if x not in dict1[k])
        else:
            dict1[k] = v
    return dict1


def merge_packs(packs: list[Path], dest: Path) -> None:
    """Later packs overwrite earlier ones; conflicting .json objects are deep-merged."""
    files: dict[str, bytes] = {}
    for pack in packs:
        for rel, path in iter_files(pack):
            data = path.read_bytes()
            if rel in files and rel.endswith(".json"):
                try:
                    d1, d2 = json.loads(files[rel]), json.loads(data)
                    if isinstance(d1, dict) and isinstance(d2, dict):
                        data = json.dumps(merge_dicts(d1, d2), indent=2, ensure_ascii=False).encode()
                except ValueError as e:
                    print(f"  warning: couldn't merge {rel}, overwriting ({e})")
            files[rel] = data

    if "pack.mcmeta" in files:
        try:
            mcmeta = json.loads(files["pack.mcmeta"])
            mcmeta["pack"]["description"] = MERGED_DESCRIPTION
            files["pack.mcmeta"] = json.dumps(mcmeta, indent=2, ensure_ascii=False).encode()
        except (ValueError, KeyError):
            pass

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, data in sorted(files.items()):
            zf.writestr(rel, data)


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    data_out = OUTPUT / "data"
    resources_out = OUTPUT / "resources"
    data_out.mkdir(parents=True)
    resources_out.mkdir()

    print("Datapacks:")
    for entry in sorted(SOURCE.iterdir()):
        if entry == HERE:
            continue
        if entry.is_dir():
            zip_folder(entry, data_out / f"{entry.name}.zip")
            print(f"  zipped  {entry.name}")
        elif entry.suffix.lower() == ".zip":
            shutil.copy2(entry, data_out / entry.name)
            print(f"  copied  {entry.name}")

    print("Resourcepacks:")
    merge_packs([RESOURCEPACKS / name for name in MERGED_SOURCES], resources_out / f"{MERGED_NAME}.zip")
    print(f"  merged  {' + '.join(MERGED_SOURCES)} -> {MERGED_NAME}")

    print(f"\nDone -> {OUTPUT}")


if __name__ == "__main__":
    main()
