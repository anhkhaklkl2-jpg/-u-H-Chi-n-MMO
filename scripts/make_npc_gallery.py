"""Catalog NPC actors from the Ninja Adventure pack into assets/npc_gallery/.

For every Actor/<group>/<name> folder (Character / Monster / Animal) the
script writes:

    assets/npc_gallery/<group>/<name>/
        preview.png     — Faceset.png when present, else the first idle frame
                          cropped from SpriteSheet.png (16x16, bottom cell of
                          the first column = facing-down idle in this pack)
        spritesheet.png — the actor's SpriteSheet.png copied verbatim
        info.txt        — source path + what's inside (faceset/walk sheet)

So mik can browse the folders in Explorer and pick a sprite for a new NPC by
name. Rerunning refreshes/extends the gallery; folders for actors removed
from the pack stay (harmless).
"""
import shutil
import sys
from pathlib import Path

from PIL import Image

PACK = Path("Nơilấyassetsngoài/Ninja Adventure - Asset Pack/Ninja Adventure - Asset Pack/Actor")
OUT = Path("assets/npc_gallery")
CELL = 16  # Ninja Adventure base cell size


def make_preview(folder: Path, dest: Path) -> str:
    """Faceset when available; else crop the down-facing idle cell."""
    faceset = folder / "Faceset.png"
    if faceset.exists():
        shutil.copyfile(faceset, dest)
        return "faceset"
    sheet = folder / "SpriteSheet.png"
    if not sheet.exists():
        return "none"
    img = Image.open(sheet).convert("RGBA")
    # Character sheets: 4 columns (down/up/left/right) x 3 rows; column 0
    # row 0 is the down-facing idle. Monster sheets are usually 2x2 — same
    # top-left cell works. Guard against sub-16px oddities by clamping.
    w, h = img.size
    cw = min(CELL, w)
    ch = min(CELL, h)
    cell = img.crop((0, 0, cw, ch))
    cell = cell.resize((cw * 4, ch * 4), Image.NEAREST)  # 4x for easy viewing
    cell.save(dest)
    return "idle-crop"


def main() -> int:
    if not PACK.exists():
        print(f"Pack not found: {PACK}")
        return 1
    total = 0
    for group in sorted(p for p in PACK.iterdir() if p.is_dir()):
        for actor in sorted(p for p in group.iterdir() if p.is_dir()):
            sheet = actor / "SpriteSheet.png"
            if not sheet.exists():
                continue
            dest_dir = OUT / group.name / actor.name
            dest_dir.mkdir(parents=True, exist_ok=True)
            kind = make_preview(actor, dest_dir / "preview.png")
            shutil.copyfile(sheet, dest_dir / "spritesheet.png")
            walk = actor / "SeparateAnim" / "Walk.png"
            notes = [
                f"actor: {actor.name}",
                f"group: {group.name}",
                f"source: {actor}",
                f"preview: {kind}",
                f"spritesheet: SpriteSheet.png ({Image.open(sheet).size[0]}x{Image.open(sheet).size[1]} px)",
            ]
            if walk.exists():
                shutil.copyfile(walk, dest_dir / "walk.png")
                notes.append("walk: SeparateAnim/Walk.png (4 facing rows x 4 frames, 16px cells)")
            (dest_dir / "info.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")
            total += 1
    print(f"cataloged {total} actors -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
