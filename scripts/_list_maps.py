import glob, os

maps = []
for p in glob.glob("assets/maps/*.json") + glob.glob("assets/maps/ekonia/*.json") + glob.glob("assets/maps/kaetram/*.json"):
    maps.append(os.path.relpath(p, "assets/maps").replace("\\", "/").replace(".json", ""))
maps.sort()
print(len(maps))
for m in maps:
    print(m)
