# m4_addon_tools_gui.py (edited)
# PyQt6 GUI for Aircraft Pipeline (Windows)
# Added: interactive hexagonal graphs for six Graph* stats which sync with text inputs

import sys
import os
import json
import copy
import re
import math
from functools import partial
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QIcon, QPainter, QPen, QBrush, QColor, QFont
import subprocess
import tempfile
import shutil
from pathlib import Path

# ---------------------------
# Paths
# ---------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    EXE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = BASE_DIR

DEFAULT_DATA_DIR = os.path.join(BASE_DIR, "Data")
OUTPUT_DIR = os.path.join(EXE_DIR, "Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
# path to UAssetGUI executable - user must set this or put UAssetGUI in PATH
UASSETGUI_EXE = (DEFAULT_DATA_DIR+"/UAssetGUI.exe")  # <- update this to where you put UAssetGUI (or "UAssetGUI" if it's in PATH)


# ---------------------------
# Stats fields
# ---------------------------
STATS_FIELDS = [
    "GunLoadCount", "MainWeaponLoadCount", "SpWeaponLoadCount1", "SpWeaponLoadCount2", "SpWeaponLoadCount3",
    "GraphAirToAir", "GraphAirToGround", "GraphSpeed", "GraphMobirity",
    "GraphStability", "GraphDefense", "PartsSlotBody", "PartsSlotArms",
    "PartsSlotMisc", "StealthLevel", "AircraftCost", "MaxHealth"
]

# Fields that use the hexagon widget (must be present in STATS_FIELDS)
HEX_FIELDS = [
    "GraphAirToAir",
    "GraphAirToGround",
    "GraphSpeed",
    "GraphMobirity",
    "GraphStability",
    "GraphDefense",
]

# Abbreviations for hex graph
HEX_ABBRS = {
    "GraphAirToAir": "A2A",
    "GraphAirToGround": "A2G",
    "GraphSpeed": "SPD",
    "GraphMobirity": "MOB",
    "GraphStability": "STB",
    "GraphDefense": "DEF",
}

# --- helper utilities ---
def run_cmd(cmd, timeout=60):
    """Run cmd (list) and raise subprocess.CalledProcessError on failure; returns stdout."""
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc.stdout

# def ensure_uassetgui_available():
#     if not shutil.which(UASSETGUI_EXE) and not Path(UASSETGUI_EXE).exists():
#         raise FileNotFoundError(f"UAssetGUI executable not found at '{UASSETGUI_EXE}'. Download UAssetGUI (releases) or set UASSETGUI_EXE correctly. See UASSETGUI README for binaries. ")
#     return True

# def uasset_to_json(uasset_path: str, out_json_path: str, engine_version: str = "VER_UE4_18", aes_hex: str = "0x68747470733A2F2F616365372E616365636F6D6261742E6A702F737065636961"):
#     ensure_uassetgui_available()
#     cmd = [UASSETGUI_EXE, "tojson", uasset_path, out_json_path, engine_version]
#     run_cmd(cmd, timeout=120)

# def json_to_uasset(json_path: str, out_uasset_like_path: str, mappings_name: str = None):
#     ensure_uassetgui_available()
#     cmd = [UASSETGUI_EXE, "fromjson", json_path, out_uasset_like_path]
#     if mappings_name:
#         cmd.append(mappings_name)
#     run_cmd(cmd, timeout=120)

def _find_uassetgui_exe():
    """
    Resolve the UAssetGUI executable.
    Priority:
      1. If UASSETGUI_EXE is an absolute/relative path that exists -> use it.
      2. Try shutil.which on the literal "UAssetGUI.exe" and "UAssetGUI".
      3. Try shutil.which on the configured UASSETGUI_EXE (in case user set just a name).
    Returns the executable path string or None.
    """
    # 1) If configured path exists, prefer that
    if UASSETGUI_EXE:
        try:
            p = Path(UASSETGUI_EXE)
            if p.exists() and os.access(str(p), os.X_OK):
                return str(p)
        except Exception:
            pass

    # 2) common names on PATH
    for name in ("UAssetGUI.exe", "UAssetGUI"):
        found = shutil.which(name)
        if found:
            return found

    # 3) try the configured value with shutil.which in case it's a simple name
    try:
        found = shutil.which(UASSETGUI_EXE)
        if found:
            return found
    except Exception:
        pass

    return None


def ensure_uassetgui_available():
    """
    Ensure we can run the UAssetGUI binary. Returns the resolved executable path (string).
    Raises FileNotFoundError with a helpful message if not found.
    """
    exe = _find_uassetgui_exe()
    if exe is None:
        raise FileNotFoundError(
            "UAssetGUI executable not found. Put UAssetGUI.exe in the Data/ folder or install it on PATH, "
            "or set UASSETGUI_EXE to its full path. See UAssetGUI README for binaries."
        )
    return exe


def uasset_to_json(uasset_path: str, out_json_path: str, engine_version: str = "VER_UE4_18", aes_hex: str = None):
    """
    Convert .uasset -> .json using UAssetGUI. Raises RuntimeError with stdout/stderr if the command fails.
    """
    exe = ensure_uassetgui_available()
    cmd = [exe, "tojson", uasset_path, out_json_path, engine_version]
    if aes_hex:
        cmd.append(aes_hex)
    try:
        out = run_cmd(cmd, timeout=180)
        return out
    except Exception as e:
        # wrap into clearer error
        raise RuntimeError(f"uasset_to_json failed: {e}")


def json_to_uasset(json_path: str, out_uasset_like_path: str, engine_version: str = "VER_UE4_18", aes_hex: str = None, mappings_name: str = None):
    """
    Convert .json -> .uasset using UAssetGUI. Returns stdout. Raises RuntimeError with stdout/stderr on failure.
    We include engine_version and optional aes_hex to match UAssetGUI expectations.
    """
    exe = ensure_uassetgui_available()
    cmd = [exe, "fromjson", json_path, out_uasset_like_path, engine_version]
    if aes_hex:
        cmd.append(aes_hex)
    if mappings_name:
        cmd.append(mappings_name)

    try:
        out = run_cmd(cmd, timeout=300)
        return out
    except Exception as e:
        # ensure helpful message
        raise RuntimeError(f"json_to_uasset failed: {e}")

# ---------------------------
# Utility
# ---------------------------
def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return OUTPUT_DIR

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ---------------------------
# Pipeline functions (based on your originals)
# ---------------------------
def add_or_edit_player_plane(input_json_path, data_dir, exe_dir, ui_values, mode, logger):
    template_path = os.path.join(DEFAULT_DATA_DIR, "player_plane_template.json")
    output_path = os.path.join(ensure_output_dir(), "PlayerPlaneDataTable.json")

    data = load_json(input_json_path)
    template = load_json(template_path)
    data_array = data["Exports"][0]["Table"]["Data"]

    # find f18f reference (for defaults)
    f18f_template = next(
        (item for item in data_array if any(
            p.get("Name") == "PlaneStringID" and p.get("Value") == "f18f"
            for p in item.get("Value", [])
        )),
        None
    )

    plane_string_id = ui_values["plane_string_id"]
    new_plane_id = ui_values["plane_id"]

    existing_entry = next(
        (d for d in data_array if any(
            p.get("Name") == "PlaneStringID" and p.get("Value") == plane_string_id
            for p in d.get("Value", [])
        )),
        None
    )

    if mode == "edit" and existing_entry:
        logger(f"[PlayerPlane] Editing existing plane {plane_string_id}")
        new_element = existing_entry
    else:
        logger(f"[PlayerPlane] Adding new plane {plane_string_id}")
        new_element = copy.deepcopy(template)
        # Name will be adjusted properly; PlaneID set below
        new_element["Name"] = f"Row_{new_plane_id or 9999}"
        data_array.append(new_element)

    def f18f_default(name):
        if f18f_template:
            return next((p.get("Value") for p in f18f_template["Value"] if p.get("Name") == name), 0)
        return 0

    # Build canonical SoftObjectPath dict used in this file format
    def make_soft_object_path_for(plane_str):
        asset_name = f"/Game/Blueprint/Player/Pawn/AcePlayerPawn_{plane_str}.AcePlayerPawn_{plane_str}_C"
        return {
            "$type": "UAssetAPI.PropertyTypes.Objects.FSoftObjectPath, UAssetAPI",
            "AssetPath": {
                "$type": "UAssetAPI.PropertyTypes.Objects.FTopLevelAssetPath, UAssetAPI",
                "PackageName": None,
                "AssetName": asset_name
            },
            "SubPathString": None
        }

    # Walk properties and set values
    for prop in new_element.get("Value", []):
        name = prop.get("Name")
        if name == "PlaneID":
            # Only set PlaneID when adding; in edit mode we must NOT change it
            if mode == "add":
                prop["Value"] = new_plane_id or prop.get("Value", 101)
        elif name == "PlaneStringID":
            prop["Value"] = plane_string_id
        elif name == "Category":
            prop["Value"] = f'EPlaneCategory::{ui_values.get("category","Fighter")}'
        elif name == "FlareLoadCount":
            if ui_values.get("flare_count", -1) != -1:
                prop["Value"] = ui_values["flare_count"]
        elif name == "SpWeaponID1":
            prop["Value"] = ui_values.get("spweapon1", "")
        elif name == "SpWeaponID2":
            prop["Value"] = ui_values.get("spweapon2", "")
        elif name == "SpWeaponID3":
            prop["Value"] = ui_values.get("spweapon3", "")
        elif name == "Reference":
            # Update the Reference nested structure so AssetName points at the plane_string_id
            existing_val = prop.get("Value")
            soft_obj = make_soft_object_path_for(plane_string_id)
            # If the existing value is a dict with an AssetPath, update in-place to preserve surrounding structure
            if isinstance(existing_val, dict) and "AssetPath" in existing_val:
                try:
                    existing_val["AssetPath"]["AssetName"] = soft_obj["AssetPath"]["AssetName"]
                    # keep SubPathString if present; otherwise set to None
                    if "SubPathString" not in existing_val:
                        existing_val["SubPathString"] = None
                    prop["Value"] = existing_val
                except Exception:
                    # fallback to canonical form
                    prop["Value"] = soft_obj
            else:
                # Not the expected structure - replace with canonical structured value
                prop["Value"] = soft_obj
        elif name in ui_values.get("stat_values", {}):
            prop["Value"] = ui_values["stat_values"][name]
        elif name in STATS_FIELDS:
            # use f18f default if present, otherwise leave whatever is in template/entry
            prop["Value"] = ui_values.get("stat_values", {}).get(
                name,
                f18f_default(name) if mode == "add" else prop.get("Value", f18f_default(name))
            )

            # --- ensure correct sorting numbers ---
    # Gather all plane IDs (including the new/edited one)
    all_ids = []
    for entry in data_array:
        pid = next((p.get("Value") for p in entry["Value"] if p.get("Name") == "PlaneStringID"), None)
        if pid:
            all_ids.append(pid)
    all_ids = sorted(set(all_ids))

    # Compute alphabetical index for this plane
    alpha_index = all_ids.index(plane_string_id)

    for prop in new_element.get("Value", []):
        if prop.get("Name") == "AlphabeticalSortNumber":
            prop["Value"] = alpha_index
        elif prop.get("Name") == "SortNumber":
            # Usually matches alpha_index, but if your JSON uses a base offset you can add it here
            prop["Value"] = alpha_index


        # Ensure "Reference" and the plane_string_id are in the NameMap
    if "NameMap" in data:
        if f"/Game/Blueprint/Player/Pawn/AcePlayerPawn_{plane_string_id}.AcePlayerPawn_{plane_string_id}_C" not in data["NameMap"]:
            data["NameMap"].append(f"/Game/Blueprint/Player/Pawn/AcePlayerPawn_{plane_string_id}.AcePlayerPawn_{plane_string_id}_C")
        if f"/Game/Blueprint/Player/Pawn/AcePlayerPawn_{plane_string_id}" not in data["NameMap"]:
            data["NameMap"].append(f"/Game/Blueprint/Player/Pawn/AcePlayerPawn_{plane_string_id}")
        # if plane_string_id not in data["NameMap"]:
        #     data["NameMap"].append(plane_string_id)

    save_json(data, output_path)
    logger(f"[PlayerPlane] Wrote: {output_path}")
    return output_path



def add_or_edit_skins(input_json_path, data_dir, exe_dir, plane_string_id, skins, mode, logger):
    template_path = os.path.join(DEFAULT_DATA_DIR, "skin_template.json")
    output_path = os.path.join(ensure_output_dir(), "SkinDataTable.json")

    data_json = load_json(input_json_path)
    template = load_json(template_path)
    data_array = data_json["Exports"][0]["Table"]["Data"]

    # In edit mode remove all skins for this plane (replace-all behavior)
    if mode == "edit":
        data_array[:] = [entry for entry in data_array if not any(p.get("Name") == "PlaneStringID" and p.get("Value") == plane_string_id for p in entry["Value"])]

    # determine next available SkinID
    used_ids = sorted([entry["Value"][0]["Value"] for entry in data_array if entry["Value"]])
    next_skin_id = 101
    for uid in used_ids:
        try:
            uid_int = int(uid)
        except Exception:
            continue
        if uid_int < 101:
            continue
        if uid_int != next_skin_id:
            break
        next_skin_id += 1

    def make_entry(template_obj, skin_id, plane_id, emblems, skin_no):
        entry = json.loads(json.dumps(template_obj))
        entry["Name"] = f"Row_{skin_id}"
        for prop in entry["Value"]:
            pname = prop.get("Name")
            if pname in ("SkinID", "SortNumber"):
                prop["Value"] = skin_id
            elif pname == "SkinNo":
                prop["Value"] = skin_no
            elif pname == "PlaneStringID":
                prop["Value"] = plane_id
            elif pname == "bNoseEmblem":
                prop["Value"] = bool(emblems.get("nose", False))
            elif pname == "bWingEmblem":
                prop["Value"] = bool(emblems.get("wing", False))
            elif pname == "bTailEmblem":
                prop["Value"] = bool(emblems.get("tail", False))
            elif pname == "PlaneReference":
                # keep original behavior: skin_no==0 -> base reference ; else use suffix
                if skin_no == 0:
                    prop["Value"] = f"/Game/Blueprint/Player/Pawn/AcePlayerPawn_{plane_id}.AcePlayerPawn_{plane_id}_C"
                else:
                    suffix = f"{skin_no:02d}"
                    prop["Value"] = f"/Game/Blueprint/Player/Pawn/Skin/AcePlayerPawn_{plane_id}_s{suffix}.AcePlayerPawn_{plane_id}_s{suffix}_C"
        return entry

    for s in skins:
        entry = make_entry(template, next_skin_id, plane_string_id, s["emblems"], s["skin_no"])
        data_array.append(entry)
        next_skin_id += 1

    save_json(data_json, output_path)
    logger(f"[Skins] Wrote: {output_path}")
    return output_path

def duplicate_aircraft_viewer(input_json_path, data_dir, exe_dir, plane_string_id, logger):
    output_path = os.path.join(ensure_output_dir(), "AircraftViewerDataTable.json")

    data = load_json(input_json_path)
    table_data = data["Exports"][0]["Table"]["Data"]

    # Find entries with f04e and duplicate them, replacing PlaneStringID and incrementing AircraftViewerID
    original_f04e_entries = [entry for entry in table_data if any(
        prop.get("Name") == "PlaneStringID" and prop.get("Value") == "f04e"
        for prop in entry["Value"]
    )]

    duplicated_entries = []
    for entry in original_f04e_entries:
        new_entry = copy.deepcopy(entry)
        match = re.match(r"Row_(\d+)", new_entry["Name"])
        if match:
            new_entry["Name"] = f"Row_{int(match.group(1)) + 294}"
        for prop in new_entry["Value"]:
            if prop["Name"] == "PlaneStringID":
                prop["Value"] = plane_string_id
            elif prop["Name"] == "AircraftViewerID":
                try:
                    prop["Value"] = int(prop["Value"]) + 294
                except Exception:
                    pass
        duplicated_entries.append(new_entry)

    table_data.extend(duplicated_entries)
    save_json(data, output_path)
    logger(f"[AircraftViewer] Wrote: {output_path}")
    return output_path

def find_input_file(data_dir: str, base_name: str):
    """
    Looks for either .json or .uasset in data_dir with the given base_name.
    Returns the first path found, or raises FileNotFoundError.
    """
    json_path = Path(data_dir) / f"{base_name}.json"
    uasset_path = Path(data_dir) / f"{base_name}.uasset"
    if json_path.exists():
        return json_path
    elif uasset_path.exists():
        return uasset_path
    else:
        raise FileNotFoundError(f"Neither {json_path} nor {uasset_path} found")

def resolve_input_file(base_name: str, data_dir: str):
    """
    Resolves input file for a given table. 
    Prefers explicit .json if it exists, otherwise .uasset.
    """
    json_path = Path(data_dir) / f"{base_name}.json"
    uasset_path = Path(data_dir) / f"{base_name}.uasset"
    if json_path.exists():
        return json_path
    elif uasset_path.exists():
        return uasset_path
    else:
        raise FileNotFoundError(f"Neither {json_path} nor {uasset_path} found")

def prepare_input(base_name: str, data_dir: str, explicit: str = None, engine_version="VER_UE4_18", aes_hex="0x68747470733A2F2F616365372E616365636F6D6261742E6A702F737065636961"):
    """
    Returns a JSON path ready for pipeline usage.
    If explicit file path is provided, use it. Otherwise resolve automatically.
    """
    raw = Path(explicit) if explicit else resolve_input_file(base_name, data_dir)
    json_path = normalize_to_json(raw, engine_version, aes_hex)
    return json_path, raw

def normalize_to_json(path_or_uasset, engine_version="VER_UE4_18", aes_hex=None):
    p = Path(path_or_uasset)
    if p.suffix.lower() == ".json":
        return str(p)
    elif p.suffix.lower() == ".uasset":
        tmp = Path(tempfile.mkdtemp()) / (p.stem + ".json")
        uasset_to_json(str(p), str(tmp), engine_version, aes_hex)
        return str(tmp)
    else:
        raise ValueError("Unsupported input type: " + str(p))

# ---------------------------
# Worker thread
# ---------------------------
class PipelineThread(QtCore.QThread):
    log_signal = QtCore.pyqtSignal(str)
    finished_signal = QtCore.pyqtSignal(bool, str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            data_dir = self.params["data_dir"]
            mode = self.params["mode"]
            # allow inputs to be .json or .uasset
    
            # Replace earlier path building:
            # pp_input_raw = Path(self.params.get("pp_input")) if self.params.get("pp_input") else find_input_file(data_dir, "PlayerPlaneDataTable")
            # s_input_raw  = Path(self.params.get("s_input"))  if self.params.get("s_input")  else find_input_file(data_dir, "SkinDataTable")
            # av_input_raw = Path(self.params.get("av_input")) if self.params.get("av_input") else find_input_file(data_dir, "AircraftViewerDataTable")
    
            # pp_input = normalize_to_json(pp_input_raw)
            # s_input = normalize_to_json(s_input_raw)
            # av_input = normalize_to_json(av_input_raw)

            # def normalize_to_json(path_or_uasset):
            #     p = Path(path_or_uasset)
            #     if p.suffix.lower() == ".json":
            #         return str(p)
            #     elif p.suffix.lower() == ".uasset":
            #         # produce temp json
            #         tmp = Path(tempfile.mkdtemp()) / (p.stem + ".json")
            #         # choose appropriate engine version for that asset (you can make this user-selectable)
            #         engine_version = self.params.get("engine_version", "VER_UE4_18")
            #         aes_hex = self.params.get("aes_hex", None)
            #         uasset_to_json(str(p), str(tmp), engine_version, aes_hex)
            #         return str(tmp)
            #     else:
            #         raise ValueError("Unsupported input type: " + str(p))

            pp_input, pp_source = prepare_input("PlayerPlaneDataTable", data_dir, self.params.get("pp_input"))
            s_input,  s_source  = prepare_input("SkinDataTable", data_dir, self.params.get("s_input"))
            av_input, av_source = prepare_input("AircraftViewerDataTable", data_dir, self.params.get("av_input"))
    
            # Now call your existing functions with these JSON paths
            self.log_signal.emit("Starting pipeline...")
            self.log_signal.emit("-> PlayerPlane step")
            pp_out_json = add_or_edit_player_plane(pp_input, data_dir, EXE_DIR, self.params["player_values"], mode, self.log_signal.emit)
    
            self.log_signal.emit("-> SkinData step")
            s_out_json = add_or_edit_skins(s_input, data_dir, EXE_DIR, self.params["player_values"]["plane_string_id"], self.params["skins"], mode, self.log_signal.emit)
    
            self.log_signal.emit("-> AircraftViewer step")
            av_out_json = duplicate_aircraft_viewer(av_input, data_dir, EXE_DIR, self.params["player_values"]["plane_string_id"], self.log_signal.emit)
    
            # After JSON outputs are written, convert them back to .uasset/.uexp
            # For each JSON we produced, convert to uasset. We'll place outputs into the Output/ directory:
            try:
                out_dir = ensure_output_dir()

                def out_name(source, default):
                    stem = Path(source).stem
                    return os.path.join(out_dir, f"{stem}.uasset")

                uassetgui_exe = _find_uassetgui_exe()
                if not uassetgui_exe:
                    self.log_signal.emit("UAssetGUI not found: skipping .uasset conversion. Set UASSETGUI_EXE or put UAssetGUI on PATH.")
                else:
                    conversions = [
                        (pp_out_json, pp_source, "PlayerPlaneDataTable"),
                        (s_out_json, s_source, "SkinDataTable"),
                        (av_out_json, av_source, "AircraftViewerDataTable"),
                    ]

                    for json_file, src, label in conversions:
                        try:
                            out_uasset = out_name(src, label)
                            self.log_signal.emit(f"Converting {json_file} -> {out_uasset}")
                            json_to_uasset(
                                json_file,
                                out_uasset,
                                engine_version=self.params.get("engine_version", "VER_UE4_18"),
                                aes_hex=self.params.get("aes_hex", None),
                            )
                            self.log_signal.emit(f"Converted {label} -> {out_uasset}")

                            # cleanup JSON if uasset exists
                            if os.path.exists(out_uasset) and os.path.exists(json_file):
                                try:
                                    os.remove(json_file)
                                    self.log_signal.emit(f"Deleted intermediate JSON: {json_file}")
                                except Exception as de:
                                    self.log_signal.emit(f"Warning: could not delete {json_file}: {de}")
                        except Exception as e:
                            self.log_signal.emit(f"Failed to convert {label}: {e}")

                self.log_signal.emit("Conversion finished. uasset + uexp are in Output/.")
            except Exception as e:
                self.log_signal.emit(f"Warning: conversion step failed: {e}")
    
            self.params["data_dir"] = OUTPUT_DIR
            self.finished_signal.emit(True, "Pipeline finished successfully.")
        except Exception as e:
            self.finished_signal.emit(False, f"Pipeline failed: {e}")


# ---------------------------
# GUI widgets
# ---------------------------
class SkinRowWidget(QtWidgets.QWidget):
    def __init__(self, index=0):
        super().__init__()
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(4, 4, 4, 4)
        lbl = QtWidgets.QLabel(f"Skin #{index}")
        lbl.setFixedWidth(70)
        # store label so it can be updated when rows are renumbered
        self.lbl = lbl
        h.addWidget(lbl)
        self.skinno = QtWidgets.QSpinBox()
        self.skinno.setRange(0, 999)
        self.skinno.setValue(index)
        self.skinno.setFixedWidth(90)
        h.addWidget(self.skinno)
        self.nose = QtWidgets.QCheckBox("Nose")
        self.wing = QtWidgets.QCheckBox("Wing")
        self.tail = QtWidgets.QCheckBox("Tail")
        h.addWidget(self.nose)
        h.addWidget(self.wing)
        h.addWidget(self.tail)
        h.addStretch(1)

    def set_values(self, skin_no, emblems):
        self.skinno.setValue(int(skin_no))
        self.nose.setChecked(bool(emblems.get("nose", False)))
        self.wing.setChecked(bool(emblems.get("wing", False)))
        self.tail.setChecked(bool(emblems.get("tail", False)))

    def get(self):
        return {
            "skin_no": int(self.skinno.value()),
            "emblems": {"nose": self.nose.isChecked(), "wing": self.wing.isChecked(), "tail": self.tail.isChecked()}
        }

# ---------------------------
# Hexagonal interactive widget
# ---------------------------
class HexagonGraph(QtWidgets.QWidget):
    valuesChanged = QtCore.pyqtSignal(list)

    def __init__(self, fields=None, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.fields = fields or HEX_FIELDS
        self.values = [50] * 6
        self._active_idx = None
        self._hover_idx = None
        self._margin = 30
        self.setMouseTracking(True)

    def setValues(self, vals):
        if isinstance(vals, dict):
            self.values = [int(vals.get(f, 0)) for f in self.fields]
        else:
            self.values = [int(v) if v is not None else 0 for v in vals]
        for i in range(6):
            self.values[i] = max(0, min(100, self.values[i]))
        self.update()
        self.valuesChanged.emit(self.values)

    def getValues(self):
        return list(self.values)

    def sizeHint(self):
        return QtCore.QSize(300, 300)

    def paintEvent(self, ev):
        w = self.width(); h = self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = w / 2; cy = h / 2
        r = min(w, h) / 2 - self._margin

        # theme-aware text color
        text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
        painter.setPen(text_color)

        # outer hexagon
        points = [QtCore.QPointF(cx + r * math.cos(math.radians(-90 + i * 60)),
                                 cy + r * math.sin(math.radians(-90 + i * 60))) for i in range(6)]
        pen = QPen(QColor(40, 40, 40))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.GlobalColor.transparent)
        painter.drawPolygon(*points)

        # concentric grids
        grid_pen = QPen(QColor(200, 200, 200))
        grid_pen.setStyle(QtCore.Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        for frac in (0.25, 0.5, 0.75):
            pr = r * frac
            pnts = [QtCore.QPointF(cx + pr * math.cos(math.radians(-90 + i * 60)),
                                   cy + pr * math.sin(math.radians(-90 + i * 60))) for i in range(6)]
            painter.drawPolygon(*pnts)

        # filled polygon from values
        poly_points = []
        for i, val in enumerate(self.values):
            vr = r * (val / 100.0)
            angle = math.radians(-90 + i * 60)
            px = cx + vr * math.cos(angle)
            py = cy + vr * math.sin(angle)
            poly_points.append(QtCore.QPointF(px, py))

        # draw polygon (color = #AF0C1F)
        painter.setPen(QPen(QColor("#AF0C1F"), 2))
        painter.setBrush(QBrush(QColor(175, 12, 31, 160)))
        painter.drawPolygon(*poly_points)

        # draw handles + values
        handle_pen = QPen(QColor(30, 30, 30))
        painter.setPen(handle_pen)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        for i, p in enumerate(poly_points):
            rect = QtCore.QRectF(p.x() - 6, p.y() - 6, 12, 12)
            painter.setBrush(QBrush(QColor(220, 220, 220) if i != self._active_idx else QColor(255, 200, 100)))
            painter.drawEllipse(rect)

            # value labels (bold)
            val_font = QFont(font)
            val_font.setBold(True)
            painter.setFont(val_font)
            dx = p.x() - cx
            dy = p.y() - cy
            norm = math.hypot(dx, dy) or 1
            offx = dx / norm * 14
            offy = dy / norm * 14
            painter.setPen(text_color)
            painter.drawText(QtCore.QPointF(p.x() + offx, p.y() + offy), str(self.values[i]))

        # draw abbreviations at outer hex corners
        painter.setFont(font)  # back to normal weight
        for i, f in enumerate(self.fields):
            angle = math.radians(-90 + i * 60)
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            dx = px - cx
            dy = py - cy
            norm = math.hypot(dx, dy) or 1
            offx = dx / norm * 20
            offy = dy / norm * 20
            painter.setPen(text_color)
            painter.drawText(QtCore.QPointF(px + offx, py + offy), HEX_ABBRS.get(f, f))

    def _vertex_positions(self):
        w = self.width(); h = self.height()
        cx = w / 2; cy = h / 2
        r = min(w, h) / 2 - self._margin
        pts = []
        for i, val in enumerate(self.values):
            vr = r * (val / 100.0)
            angle = math.radians(-90 + i * 60)
            pts.append(QtCore.QPointF(cx + vr * math.cos(angle), cy + vr * math.sin(angle)))
        return pts

    def _vertex_dirs(self):
        dirs = []
        for i in range(6):
            angle = math.radians(-90 + i * 60)
            dirs.append((math.cos(angle), math.sin(angle)))
        return dirs

    def mousePressEvent(self, ev):
        pos = ev.position()
        pts = self._vertex_positions()
        best = None; best_d = 1e9
        for i, p in enumerate(pts):
            d = math.hypot(p.x() - pos.x(), p.y() - pos.y())
            if d < best_d:
                best_d = d; best = i
        if best is not None and best_d <= 14:
            self._active_idx = best
            self.update()
        else:
            dirs = self._vertex_dirs()
            cx = self.width()/2; cy = self.height()/2
            mx = pos.x() - cx; my = pos.y() - cy
            best_proj = -1e9; best_i = None
            for i, (dx, dy) in enumerate(dirs):
                proj = mx*dx + my*dy
                if proj > best_proj:
                    best_proj = proj; best_i = i
            if best_i is not None:
                self._active_idx = best_i
                self._set_value_from_pos(best_i, pos)

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        if self._active_idx is not None and (ev.buttons() & QtCore.Qt.MouseButton.LeftButton):
            self._set_value_from_pos(self._active_idx, pos)

    def mouseReleaseEvent(self, ev):
        if self._active_idx is not None:
            self._active_idx = None
            self.update()

    def _set_value_from_pos(self, idx, pos):
        w = self.width(); h = self.height()
        cx = w / 2; cy = h / 2
        mx = pos.x() - cx; my = pos.y() - cy
        dx, dy = self._vertex_dirs()[idx]
        proj = mx*dx + my*dy
        rmax = min(w, h) / 2 - self._margin
        val = int(round((proj / rmax) * 100))
        val = max(0, min(100, val))
        if self.values[idx] != val:
            self.values[idx] = val
            self.update()
            self.valuesChanged.emit(self.getValues())


# ---------------------------
# Main Window
# ---------------------------
# ---------------------------
# Main Window
# ---------------------------
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        main = QtWidgets.QVBoxLayout(self)

        # --- Data / input selectors ---
        files_row = QtWidgets.QHBoxLayout()
        main.addLayout(files_row)
        files_row.addWidget(QtWidgets.QLabel("Data folder:"))
        self.data_dir_edit = QtWidgets.QLineEdit(DEFAULT_DATA_DIR)
        files_row.addWidget(self.data_dir_edit)
        btn_browse_data = QtWidgets.QPushButton("Browse")
        btn_browse_data.clicked.connect(self.browse_data_dir)
        files_row.addWidget(btn_browse_data)

        # per-file overrides
        file_over_row = QtWidgets.QHBoxLayout()
        main.addLayout(file_over_row)
        self.pp_input_edit = QtWidgets.QLineEdit(str(resolve_input_file("PlayerPlaneDataTable",self.data_dir_edit.text())))
        file_over_row.addWidget(QtWidgets.QLabel("PlayerPlaneDataTable input:"))
        file_over_row.addWidget(self.pp_input_edit)
        btn_pp = QtWidgets.QPushButton("Browse")
        btn_pp.clicked.connect(lambda: self.browse_file(self.pp_input_edit))
        file_over_row.addWidget(btn_pp)

        self.skin_input_edit = QtWidgets.QLineEdit(str(resolve_input_file("SkinDataTable",self.data_dir_edit.text())))
        file_over_row.addWidget(QtWidgets.QLabel("SkinDataTable input:"))
        file_over_row.addWidget(self.skin_input_edit)
        btn_skin = QtWidgets.QPushButton("Browse")
        btn_skin.clicked.connect(lambda: self.browse_file(self.skin_input_edit))
        file_over_row.addWidget(btn_skin)

        av_row = QtWidgets.QHBoxLayout()
        main.addLayout(av_row)
        self.av_input_edit = QtWidgets.QLineEdit(str(resolve_input_file("AircraftViewerDataTable",self.data_dir_edit.text())))
        av_row.addWidget(QtWidgets.QLabel("AircraftViewerDataTable input:"))
        av_row.addWidget(self.av_input_edit)
        btn_av = QtWidgets.QPushButton("Browse")
        btn_av.clicked.connect(lambda: self.browse_file(self.av_input_edit))
        av_row.addWidget(btn_av)

        # -------------------
        # Add/Edit plane controls (outside tabs)
        # -------------------
        mode_row = QtWidgets.QHBoxLayout()
        self.add_radio = QtWidgets.QRadioButton("Add new plane")
        self.add_radio.setChecked(True)
        self.edit_radio = QtWidgets.QRadioButton("Edit existing plane")
        mode_row.addWidget(self.add_radio)
        mode_row.addWidget(self.edit_radio)
        main.addLayout(mode_row)

        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_group.addButton(self.add_radio)
        self.mode_group.addButton(self.edit_radio)

        select_row = QtWidgets.QHBoxLayout()
        self.existing_label = QtWidgets.QLabel("Select existing plane:")
        self.existing_combo = QtWidgets.QComboBox()
        select_row.addWidget(self.existing_label)
        select_row.addWidget(self.existing_combo)
        main.addLayout(select_row)

        # start in Add mode: hide selector
        self.existing_label.hide()
        self.existing_combo.hide()

        # -------------------
        # Tabs
        # -------------------
        self.tabs = QtWidgets.QTabWidget()
        main.addWidget(self.tabs)

        # -------------------
        # PlayerPlane tab
        # -------------------
        pp_tab = QtWidgets.QWidget()
        pp_layout = QtWidgets.QVBoxLayout(pp_tab)

        form = QtWidgets.QFormLayout()
        self.plane_string_label = QtWidgets.QLabel("PlaneStringID:")
        self.plane_string = QtWidgets.QLineEdit()
        form.addRow(self.plane_string_label, self.plane_string)

        self.plane_id_label = QtWidgets.QLabel("PlaneID:")
        self.plane_id_edit = QtWidgets.QLineEdit()
        form.addRow(self.plane_id_label, self.plane_id_edit)

        self.category_label = QtWidgets.QLabel("Category:")
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.addItems(["Fighter", "Attacker", "Multirole"])
        form.addRow(self.category_label, self.category_combo)

        self.flare_label = QtWidgets.QLabel("FlareLoadCount:")
        self.flare_spin = QtWidgets.QSpinBox()
        self.flare_spin.setRange(-1, 9999)
        self.flare_spin.setValue(-1)
        form.addRow(self.flare_label, self.flare_spin)

        self.sp1 = QtWidgets.QLineEdit(); self.sp2 = QtWidgets.QLineEdit(); self.sp3 = QtWidgets.QLineEdit()
        form.addRow(QtWidgets.QLabel("SpWeaponID1:"), self.sp1)
        form.addRow(QtWidgets.QLabel("SpWeaponID2:"), self.sp2)
        form.addRow(QtWidgets.QLabel("SpWeaponID3:"), self.sp3)

        pp_layout.addLayout(form)

        # Stats group
        stats_group = QtWidgets.QGroupBox("Plane stats (leave empty to use defaults)")
        stats_grid = QtWidgets.QGridLayout(stats_group)
        self.stat_edits = {}
        for i, name in enumerate(STATS_FIELDS):
            lbl = QtWidgets.QLabel(name + ":")
            le = QtWidgets.QLineEdit()
            le.setPlaceholderText("default")
            self.stat_edits[name] = le
            stats_grid.addWidget(lbl, i // 2, (i % 2) * 2)
            stats_grid.addWidget(le, i // 2, (i % 2) * 2 + 1)

        
        stats_scroll = QtWidgets.QScrollArea()
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setWidget(stats_group)
        stats_scroll.setFixedHeight(300)

        # Insert hexagon widget to the left of the stats
        hex_and_stats = QtWidgets.QHBoxLayout()
        self.hex_widget = HexagonGraph(fields=HEX_FIELDS)
        hex_and_stats.addWidget(self.hex_widget)
        hex_and_stats.addWidget(stats_scroll)
        pp_layout.addLayout(hex_and_stats)

        self.tabs.addTab(pp_tab, "PlayerPlaneDataTable")

        pp_layout.addWidget(QtWidgets.QLabel("Note: GraphXXX stats determine the stats' visual representation in the hangar view's stats graph. Functional stats are managed by the plane's PlayerPlaneConfig file."))

        # -------------------
        # Skin tab
        # -------------------
        skins_tab = QtWidgets.QWidget()
        skins_layout = QtWidgets.QVBoxLayout(skins_tab)

        top_h = QtWidgets.QHBoxLayout()
        top_h.addWidget(QtWidgets.QLabel("Number of skins:"))
        self.skin_count_spin = QtWidgets.QSpinBox()
        self.skin_count_spin.setRange(0, 200)
        self.skin_count_spin.valueChanged.connect(self.rebuild_skins_from_spin)
        top_h.addWidget(self.skin_count_spin)
        skins_layout.addLayout(top_h)

        self.skin_scroll = QtWidgets.QScrollArea()
        self.skin_scroll.setWidgetResizable(True)
        self.skin_container = QtWidgets.QWidget()
        self.skin_layout = QtWidgets.QVBoxLayout(self.skin_container)
        self.skin_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.skin_scroll.setWidget(self.skin_container)
        skins_layout.addWidget(self.skin_scroll)

        self.skin_rows = []
        self.tabs.addTab(skins_tab, "SkinDataTable")

        # Log & Run
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(180)
        main.addWidget(self.log)

        self.run_btn = QtWidgets.QPushButton("Run pipeline")
        self.run_btn.setFixedHeight(48)
        main.addWidget(self.run_btn)

        # Signals
        self.run_btn.clicked.connect(self.start_pipeline)
        self.edit_radio.toggled.connect(self.toggle_mode)
        self.existing_combo.currentTextChanged.connect(self.on_existing_selected)

        self.try_fill_placeholders()

        self.loaded_plane_id = None
        self.setLayout(main)
        self.setWindowTitle("M4AddonToolsGUI")
        try:
            self.setWindowIcon(QIcon(DEFAULT_DATA_DIR+"/gui.ico"))
        except Exception:
            pass
        self.resize(1020, 820)

        # initialize placeholders (if defaults exist)
        self.try_fill_placeholders()

        # internal state
        self.loaded_plane_id = None

        # Connect hex widget <-> stat edits synchronization
        self.hex_widget.valuesChanged.connect(self.on_hex_values_changed)
        for fname in HEX_FIELDS:
            if fname in self.stat_edits:
                le = self.stat_edits[fname]
                le.editingFinished.connect(partial(self.on_stat_edit_changed, fname))

        self.setLayout(main)

    # -------------------------
    # UI helpers
    # -------------------------
    def browse_data_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Data folder", self.data_dir_edit.text() or DEFAULT_DATA_DIR)
        if d:
            self.data_dir_edit.setText(d)
            self.update_default_input_paths(d)

    def browse_file(self, line_edit):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select input file",
            self.data_dir_edit.text() or DEFAULT_DATA_DIR,
            "Data Files (*.json *.uasset);;All Files (*)"
        )

        if fname:
            line_edit.setText(fname)
            # If the user changed the PlayerPlaneDataTable override, refresh the existing-plane list
            if line_edit is self.pp_input_edit:
                self.refresh_existing_planes()

    def update_default_input_paths(self, new_path):
        """
        Update the input locations (pp_input_edit, skin_input_edit, av_input_edit)
        to match the new Data folder. Prefers .uasset if present, else .json.
        """
        def resolve_for(base_name):
            uasset_path = os.path.join(new_path, f"{base_name}.uasset")
            json_path = os.path.join(new_path, f"{base_name}.json")
            if os.path.exists(uasset_path):
                return uasset_path
            elif os.path.exists(json_path):
                return json_path
            return ""

        self.pp_input_edit.setText(resolve_for("PlayerPlaneDataTable"))
        self.skin_input_edit.setText(resolve_for("SkinDataTable"))
        self.av_input_edit.setText(resolve_for("AircraftViewerDataTable"))

        # Refresh combo box for existing planes
        self.refresh_existing_planes()


    def try_fill_placeholders(self):
        try:
            ppdt = resolve_input_file("PlayerPlaneDataTable", DEFAULT_DATA_DIR)
            if os.path.exists(ppdt):
                pp_json = normalize_to_json(ppdt)
                d = load_json(pp_json)
                data_array = d["Exports"][0]["Table"]["Data"]
                f18f_template = next((item for item in data_array if any(p.get("Name") == "PlaneStringID" and p.get("Value") == "f18f" for p in item.get("Value", []))), None)
                if f18f_template:
                    for name in STATS_FIELDS:
                        val = next((p.get("Value") for p in f18f_template["Value"] if p.get("Name") == name), None)
                        if val is not None and name in self.stat_edits:
                            self.stat_edits[name].setPlaceholderText(str(val))
        except Exception:
            pass

    def toggle_mode(self, checked):
        if checked:
            self.refresh_existing_planes()
            self.existing_label.show(); self.existing_combo.show()
            self.plane_string_label.hide(); self.plane_string.hide()
            self.plane_id_label.hide(); self.plane_id_edit.hide()
            current_plane = self.existing_combo.currentText()
            if current_plane:
                self.on_existing_selected(current_plane)
        else:
            self.existing_label.hide(); self.existing_combo.hide()
            self.plane_string_label.show(); self.plane_string.show()
            self.plane_id_label.show(); self.plane_id_edit.show()
            self.loaded_plane_id = None
            self.plane_id_edit.clear()

    # ... rest of functions (rebuild_skins_from_spin, renumber_skin_rows, clear_skin_rows,
    # refresh_existing_planes, on_existing_selected, populate_skin_rows_from_models, start_pipeline, on_pipeline_finished)

    # The following methods are unchanged from the original file; they are included in the actual
    # edited file so the program remains fully functional.

    def rebuild_skins_from_spin(self, count):
        try:
            current = len(self.skin_rows)
            if count == current:
                return

            if count < current:
                for i in range(current - 1, count - 1, -1):
                    w = self.skin_rows.pop(i)
                    w.setParent(None)
                    w.deleteLater()
            else:
                for i in range(current, count):
                    row = SkinRowWidget(i)
                    self.skin_layout.addWidget(row)
                    self.skin_rows.append(row)

            self.renumber_skin_rows()
        except Exception as e:
            self.log.append(f"Failed to rebuild skin rows: {e}")

    def renumber_skin_rows(self):
        for idx, w in enumerate(self.skin_rows):
            try:
                w.lbl.setText(f"Skin #{idx}")
            except Exception:
                pass

    def clear_skin_rows(self):
        for w in self.skin_rows:
            w.setParent(None)
            w.deleteLater()
        self.skin_rows = []

    def refresh_existing_planes(self):
        try:
            try:
                pp_path = self.pp_input_edit.text().strip()
                if not pp_path:
                    pp_path = resolve_input_file("PlayerPlaneDataTable", self.data_dir_edit.text() or DEFAULT_DATA_DIR)
                pp_json = normalize_to_json(pp_path)
                data = load_json(pp_json)
            except Exception:
                data = {"Exports": [{"Table": {"Data": []}}]}
            planes = [p.get("Value") for d in data["Exports"][0]["Table"]["Data"] for p in d["Value"] if p.get("Name") == "PlaneStringID"]
            unique_sorted = sorted(set([x for x in planes if x]))
            current = self.existing_combo.currentText()
            self.existing_combo.blockSignals(True)
            self.existing_combo.clear()
            self.existing_combo.addItems(unique_sorted)
            if current and current in unique_sorted:
                idx = self.existing_combo.findText(current)
                if idx >= 0:
                    self.existing_combo.setCurrentIndex(idx)
            self.existing_combo.blockSignals(False)
        except Exception as e:
            self.existing_combo.clear()
            self.log.append(f"Failed to refresh plane list: {e}")

    def on_existing_selected(self, plane_string):
        if not plane_string:
            return
        try:
            pp_path = self.pp_input_edit.text().strip()
            if not pp_path:
                pp_path = resolve_input_file("PlayerPlaneDataTable", self.data_dir_edit.text() or DEFAULT_DATA_DIR)
            if not os.path.exists(pp_path):
                self.log.append(f"PlayerPlaneDataTable not found: {pp_path}")
                return
            pp_json = normalize_to_json(pp_path)
            data = load_json(pp_json)
            entry = next((d for d in data["Exports"][0]["Table"]["Data"] if any(p.get("Name") == "PlaneStringID" and p.get("Value") == plane_string for p in d["Value"])), None)
            if entry:
                for name in STATS_FIELDS:
                    self.stat_edits[name].clear()
                self.loaded_plane_id = None
                for prop in entry["Value"]:
                    pname = prop.get("Name")
                    pval = prop.get("Value")
                    if pname == "PlaneID":
                        self.loaded_plane_id = int(pval) if pval is not None and str(pval).isdigit() else None
                    elif pname == "Category":
                        text = str(pval).split("::")[-1] if pval else ""
                        idx = self.category_combo.findText(text)
                        if idx >= 0:
                            self.category_combo.setCurrentIndex(idx)
                    elif pname == "FlareLoadCount":
                        try:
                            self.flare_spin.setValue(int(pval))
                        except Exception:
                            pass
                    elif pname == "SpWeaponID1":
                        self.sp1.setText(str(pval) if pval is not None else "")
                    elif pname == "SpWeaponID2":
                        self.sp2.setText(str(pval) if pval is not None else "")
                    elif pname == "SpWeaponID3":
                        self.sp3.setText(str(pval) if pval is not None else "")
                    elif pname in STATS_FIELDS:
                        try:
                            self.stat_edits[pname].setText(str(int(pval)))
                        except Exception:
                            self.stat_edits[pname].setText(str(pval) if pval is not None else "")
                if self.loaded_plane_id is not None:
                    self.plane_id_edit.setText(str(self.loaded_plane_id))
                else:
                    self.plane_id_edit.clear()

            sdt_path = self.skin_input_edit.text().strip()
            if not sdt_path:
                sdt_path = os.path.join(self.data_dir_edit.text() or DEFAULT_DATA_DIR, "SkinDataTable.json")
            if not os.path.exists(sdt_path):
                self.populate_skin_rows_from_models([])
                return
            s_json = normalize_to_json(sdt_path)
            sdata = load_json(s_json)
            skin_entries = [d for d in sdata["Exports"][0]["Table"]["Data"] if any(p.get("Name") == "PlaneStringID" and p.get("Value") == plane_string for p in d["Value"])]
            skins = []
            for s in skin_entries:
                skin_no = 0
                emblems = {"nose": False, "wing": False, "tail": False}
                for p in s["Value"]:
                    if p.get("Name") == "SkinNo":
                        try: skin_no = int(p.get("Value"))
                        except: skin_no = 0
                    elif p.get("Name") == "bNoseEmblem":
                        emblems["nose"] = bool(p.get("Value"))
                    elif p.get("Name") == "bWingEmblem":
                        emblems["wing"] = bool(p.get("Value"))
                    elif p.get("Name") == "bTailEmblem":
                        emblems["tail"] = bool(p.get("Value"))
                skins.append({"skin_no": skin_no, "emblems": emblems})
            self.populate_skin_rows_from_models(skins)
            vals = [int(self.stat_edits[f].text().strip() or 0) for f in HEX_FIELDS]
            self.hex_widget.setValues(vals)
        except Exception as e:
            self.log.append(f"Failed to load existing plane: {e}")

    def populate_skin_rows_from_models(self, skins):
        self.clear_skin_rows()
        for i, sk in enumerate(skins):
            row = SkinRowWidget(i)
            row.set_values(sk.get("skin_no", i), sk.get("emblems", {}))
            self.skin_layout.addWidget(row)
            self.skin_rows.append(row)
        self.skin_count_spin.blockSignals(True)
        self.skin_count_spin.setValue(len(self.skin_rows))
        self.skin_count_spin.blockSignals(False)
        self.renumber_skin_rows()

    def start_pipeline(self):
        try:
            mode = "edit" if self.edit_radio.isChecked() else "add"
            ppdt_path = self.pp_input_edit.text().strip()
            if ppdt_path and os.path.exists(ppdt_path):
                data_dir = os.path.dirname(ppdt_path)
            else:
                data_dir = self.data_dir_edit.text() or DEFAULT_DATA_DIR

            ppdt = normalize_to_json(resolve_input_file("PlayerPlaneDataTable", data_dir))
            data = load_json(ppdt)
            next_free_plane_id = 101
            existing_plane_ids = {p.get("Value") for d in data["Exports"][0]["Table"]["Data"] for p in d.get("Value", []) if p.get("Name") == "PlaneID"}
            while next_free_plane_id in existing_plane_ids or not (100 < next_free_plane_id <= 9999):
                next_free_plane_id += 1
                if next_free_plane_id > 9999:
                    print("No valid PlaneID available in the 101-9999 range.")
                    input("Press Enter to close...")
                    sys.exit(1)
            if mode == "edit":
                plane_string = self.existing_combo.currentText()
                plane_id = self.loaded_plane_id
            else:
                plane_string = self.plane_string.text().strip()
                plane_id = int(self.plane_id_edit.text()) if self.plane_id_edit.text().strip().isdigit() else next_free_plane_id

            if not plane_string:
                raise ValueError("PlaneStringID is required.")

            stat_values = {}
            for name, edit in self.stat_edits.items():
                txt = edit.text().strip()
                if txt != "":
                    try:
                        stat_values[name] = int(txt)
                    except Exception:
                        raise ValueError(f"Stat {name} must be an integer if provided.")

            pv = {
                "plane_string_id": plane_string,
                "plane_id": plane_id,
                "category": self.category_combo.currentText(),
                "flare_count": int(self.flare_spin.value()),
                "spweapon1": self.sp1.text().strip(),
                "spweapon2": self.sp2.text().strip(),
                "spweapon3": self.sp3.text().strip(),
                "stat_values": stat_values
            }

            if not self.skin_rows:
                raise ValueError("No skins have been added.")
            else:
                skins = [r.get() for r in self.skin_rows]

            params = {
                "data_dir": data_dir,
                "player_values": pv,
                "skins": skins,
                "mode": mode
            }

            self.run_btn.setEnabled(False)
            self.log.clear()
            self.log.append("Launching pipeline...")

            self.worker = PipelineThread(params)
            self.worker.log_signal.connect(self.log.append)
            self.worker.finished_signal.connect(self.on_pipeline_finished)
            self.worker.start()
        except Exception as e:
            self.log.append(f"Error: {e}")

    def on_pipeline_finished(self, success, message):
        self.log.append(message)
        self.run_btn.setEnabled(True)
        if success:
            # After successful run, set Data folder to Output and refresh inputs
            new_data_dir = OUTPUT_DIR
            self.data_dir_edit.setText(new_data_dir)
            # Always reload paths and plane list even if Data folder is the same
            self.update_default_input_paths(new_data_dir)
            self.refresh_existing_planes()

            QtWidgets.QMessageBox.information(
                self,
                "Pipeline",
                "Pipeline finished successfully. Data folder switched to Output/. "
                "Working files will now continue from the converted results."
            )
        else:
            QtWidgets.QMessageBox.critical(self, "Pipeline", message)


    # ---------------------------
    # Hex <-> edits synchronization handlers
    # ---------------------------
    # def on_existing_selected(self, plane_string):
    #     if not plane_string:
    #         return
    #     try:
    #         # (existing code loads plane data and sets stat_edits...)
    #         # after setting stat_edits:
    #         vals = []
    #         for f in HEX_FIELDS:
    #             txt = self.stat_edits[f].text().strip()
    #         try:
    #             vals.append(int(txt) if txt else 0)
    #         except Exception:
    #             vals.append(0)
    #         self.hex_widget.setValues(vals)
    #     except Exception as e:
    #         self.log.append(f"Failed to load existing plane: {e}")


    def on_hex_values_changed(self, values):
        for i, fname in enumerate(HEX_FIELDS):
            if fname in self.stat_edits:
                le = self.stat_edits[fname]
                le.blockSignals(True)
                le.setText(str(int(values[i])))
                le.blockSignals(False)


    def on_stat_edit_changed(self, fname):
        vals = []
        for f in HEX_FIELDS:
            txt = self.stat_edits[f].text().strip()
            try:
                v = int(txt) if txt else 0
            except Exception:
                v = 0
            vals.append(max(0, min(100, v)))
        self.hex_widget.setValues(vals)


# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
