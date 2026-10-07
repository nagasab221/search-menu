#!/usr/bin/env python3
"""Swaps Cinnamon's menu on the panel for Search Menu, or back.

    panel.py install|remove <enabled-applets> <next-applet-id> <spices dir>

Prints the new enabled-applets list and the new next-applet-id on two lines, or
nothing if the panel needs no change. Each swapped menu keeps its spot on the panel
and its settings (keyboard shortcut, icon, size...), copied to the new instance.
"""
import ast
import os
import shutil
import sys

STOCK = "menu@cinnamon.org"
OURS = "search-menu@fabri"


def fields(entry):
    # panel:zone:order:uuid:id (fresh installs may not have the id yet)
    return (entry.split(":") + [""] * 5)[:5]


def uuid_of(entry):
    return fields(entry)[3].lstrip("!")


def copy_settings(spices, src_uuid, src_id, dst_uuid, dst_id):
    src = os.path.join(spices, src_uuid, f"{src_id}.json")
    if src_id and os.path.isfile(src):
        os.makedirs(os.path.join(spices, dst_uuid), exist_ok=True)
        shutil.copy(src, os.path.join(spices, dst_uuid, f"{dst_id}.json"))


def main():
    mode, raw, counter, spices = sys.argv[1], sys.argv[2].strip(), int(sys.argv[3]), sys.argv[4]
    entries = [] if raw.startswith("@as") else ast.literal_eval(raw)
    swap_from, swap_to = (STOCK, OURS) if mode == "install" else (OURS, STOCK)

    if mode == "install" and any(uuid_of(e) == OURS for e in entries):
        return  # already on the panel

    # same way Cinnamon numbers a new applet, so nothing it adds later can clash
    next_id = max([counter, 1] + [int(fields(e)[4]) + 1 for e in entries if fields(e)[4].isdigit()])

    changed = False
    result = []
    for entry in entries:
        panel, zone, order, _, old_id = fields(entry)
        if uuid_of(entry) == swap_from:
            copy_settings(spices, swap_from, old_id, swap_to, next_id)
            entry = f"{panel}:{zone}:{order}:{swap_to}:{next_id}"
            next_id += 1
            changed = True
        result.append(entry)

    if mode == "install" and not changed:
        # no menu on the panel at all: put ours at the start of the first panel
        panels = sorted({fields(e)[0] for e in entries if fields(e)[0]}) or ["panel1"]
        panel = "panel1" if "panel1" in panels else panels[0]
        result.insert(0, f"{panel}:left:0:{OURS}:{next_id}")
        next_id += 1
        changed = True

    if changed:
        print(result)
        print(next_id)


if __name__ == "__main__":
    main()
