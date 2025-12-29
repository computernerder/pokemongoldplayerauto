#!/usr/bin/env python3
"""
run_emulator_gui.py - CustomTkinter GUI embedding PyBoy headless output with a memory panel.

This uses PyBoy in headless mode and renders frames into a Tk image. A right-side panel
shows selected memory fields via gsc_memory_lib. Keyboard bindings mirror the SDL runner:
WASD, Z/X/C/V, Enter/Space. Buttons adjust speed; F-keys are not used here.
"""

from __future__ import annotations

from pathlib import Path
import time
from tkinter import messagebox
from urllib.parse import urlparse

import customtkinter as ctk
from PIL import Image
from pyboy import PyBoy
from pyboy.utils import WindowEvent

import gsc_memory_lib as gml
import gsc_name_maps as names


ROM_PATH = (
    Path(__file__).parent
    / "Pokemon_ Gold Version"
    / "Pokemon - Gold Version (USA, Europe) (SGB Enhanced) (GB Compatible).gbc"
)
SAVE_PATH = ROM_PATH.with_suffix(".sav")
STATE_DIR = Path(__file__).parent / "states"
PERSIST_STATE = STATE_DIR / "autosave.state"
MIN_SPEED = 0.25
MAX_SPEED = 10.0

DEFAULT_WATCH_KEYS = [
    "player_x",
    "player_y",
    "map_bank",
    "map_number",
    "money",
    "party_count",
    "party[0].level",
    "party[0].hp",
    "party[0].max_hp",
    "battle_type",
    "wild_species",
    "wild_level",
]


def clamp_speed(current: float, mult: float) -> float:
    return max(MIN_SPEED, min(MAX_SPEED, current * mult))


def _make_read_mem(memory):
    return lambda addr, size: bytes(memory[addr : addr + size])


def _make_write_mem(memory):
    return lambda addr, data: memory.__setitem__(slice(addr, addr + len(data)), data)


def _fmt_value(val) -> str:
    if isinstance(val, bytes):
        hex_bytes = " ".join(f"{b:02X}" for b in val)
        return f"[{hex_bytes}]"
    if isinstance(val, int):
        return f"{val} (0x{val:X})"
    return str(val)


def decode_gsc_text(raw: bytes) -> str:
    """Best-effort decode of GSC text (upper letters/digits, stop at 0x50 terminator)."""
    out = []
    for b in raw:
        if b == 0x50:
            break
        if b in (0x7F, 0x00):
            out.append(" ")
            continue
        if 0x80 <= b <= 0x99:
            out.append(chr(ord("A") + (b - 0x80)))
            continue
        if 0xA0 <= b <= 0xB9:
            out.append(chr(ord("a") + (b - 0xA0)))
            continue
        if 0xF6 <= b <= 0xFF:
            out.append(chr(ord("0") + (b - 0xF6)))
            continue
        out.append("?")
    return "".join(out).strip()


def encode_gsc_text(text: str, size: int) -> bytes:
    """Encode a Python string into fixed-length GSC text, padding with 0x50 terminator."""
    out = bytearray()
    for ch in text:
        if len(out) >= size:
            break
        if ch == " ":
            out.append(0x7F)
        elif "A" <= ch <= "Z":
            out.append(0x80 + (ord(ch) - ord("A")))
        elif "a" <= ch <= "z":
            out.append(0xA0 + (ord(ch) - ord("a")))
        elif "0" <= ch <= "9":
            out.append(0xF6 + (ord(ch) - ord("0")))
        else:
            out.append(0x7F)
    # Pad with terminator then fill remaining with terminator if needed.
    out.append(0x50)
    while len(out) < size:
        out.append(0x50)
    return bytes(out[:size])


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return default


class EmulatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AutoPokemon GUI")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        if not ROM_PATH.exists():
            raise FileNotFoundError(f"ROM not found at {ROM_PATH}")

        STATE_DIR.mkdir(exist_ok=True)

        # Use the "null" window to avoid opening an SDL window; we render frames manually.
        # PyBoy 2.6.x lacks a savefile kwarg; we'll load/save a persistent state file instead.
        self.pyboy = PyBoy(str(ROM_PATH), window="null", scale=3, debug=False)
        self.speed = 1.0
        self.pyboy.set_emulation_speed(self.speed)
        self.speed_accum = 0.0  # accumulates fractional speed steps
        self.ctk_image = None
        self.running = True
        self._destroying = False

        self.read_mem = _make_read_mem(self.pyboy.memory)
        self.write_mem = _make_write_mem(self.pyboy.memory)
        self.ram_catalog = gml.build_ram_catalog(include_party=True)
        self._last_live_snapshot: dict[str, object] = {}
        
        # UI state
        self.paused = False
        self.active_party_slot = 0
        self.edit_buffer: dict[str, object] = {}
        self.dirty = False
        self._editing_keys: set[str] = set()

        # Online move suggestions (best-effort; safe fallback when offline)
        self._pokeapi_pokemon_cache: dict[int, dict] = {}
        self._pokeapi_move_pp_cache: dict[int, int] = {}

        # Inventory UI state
        self._inv_item_choices = [names.format_item_choice(i) for i in range(1, 256)]

        # Load persistent state if present.
        if PERSIST_STATE.exists():
            try:
                with open(PERSIST_STATE, "rb") as f:
                    self.pyboy.load_state(f)
                print(f"Loaded persistent state from {PERSIST_STATE}")
            except Exception as exc:  # noqa: BLE001
                print(f"Failed to load persistent state: {exc}")

        self._build_ui()
        self._bind_keys()

        self.last_mem_refresh = 0.0
        # Defer start slightly to let Tk finish its own setup (titlebar color, etc.).
        self.after(200, self._loop)

    def _pokeapi_extract_id(self, url: str) -> int:
        try:
            p = urlparse(url)
            parts = [seg for seg in p.path.split("/") if seg]
            if not parts:
                return 0
            return int(parts[-1], 10)
        except Exception:
            return 0

    def _pokeapi_get_pokemon(self, species_id: int) -> dict:
        if species_id in self._pokeapi_pokemon_cache:
            return self._pokeapi_pokemon_cache[species_id]
        import requests

        resp = requests.get(f"https://pokeapi.co/api/v2/pokemon/{species_id}/", timeout=6)
        resp.raise_for_status()
        data = resp.json()
        self._pokeapi_pokemon_cache[species_id] = data
        return data

    def _pokeapi_get_move_pp(self, move_id: int) -> int:
        if move_id in self._pokeapi_move_pp_cache:
            return self._pokeapi_move_pp_cache[move_id]
        import requests

        resp = requests.get(f"https://pokeapi.co/api/v2/move/{move_id}/", timeout=6)
        resp.raise_for_status()
        pp = int(resp.json().get("pp") or 0)
        self._pokeapi_move_pp_cache[move_id] = pp
        return pp

    def _suggest_moves_for_species_level(self, species_id: int, level: int) -> tuple[list[int], list[int]]:
        """Return up to 4 move IDs + PP for a species at a given level.

        Best-effort: uses PokéAPI and filters to Gold/Silver level-up moves.
        Falls back to Tackle/Growl if offline.
        """
        # Reasonable offline fallback.
        fallback_moves = [33, 45, 0, 0]
        fallback_pp = [35, 40, 0, 0]

        try:
            data = self._pokeapi_get_pokemon(int(species_id))
            learned: list[tuple[int, int]] = []
            for entry in data.get("moves", []) or []:
                move = entry.get("move") or {}
                move_id = self._pokeapi_extract_id(str(move.get("url") or ""))
                if not move_id:
                    continue

                for vd in entry.get("version_group_details", []) or []:
                    vg = (vd.get("version_group") or {}).get("name")
                    if vg != "gold-silver":
                        continue
                    method = (vd.get("move_learn_method") or {}).get("name")
                    if method != "level-up":
                        continue
                    lvl = int(vd.get("level_learned_at") or 0)
                    if lvl <= int(level):
                        learned.append((lvl, move_id))

            # Pick the last 4 distinct level-up moves <= level.
            learned.sort(key=lambda t: (t[0], t[1]))
            distinct: list[int] = []
            for _lvl, mid in learned:
                if mid not in distinct:
                    distinct.append(mid)
            move_ids = distinct[-4:]
            if not move_ids:
                return (fallback_moves, fallback_pp)

            move_ids = (move_ids + [0, 0, 0, 0])[:4]
            pp_vals: list[int] = []
            for mid in move_ids:
                if mid == 0:
                    pp_vals.append(0)
                    continue
                pp = self._pokeapi_get_move_pp(mid)
                pp_vals.append(max(1, min(63, int(pp or 1))))
            return (move_ids, pp_vals)
        except Exception:
            return (fallback_moves, fallback_pp)

    def _build_ui(self):
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        left.rowconfigure(0, weight=1)
        left.rowconfigure(1, weight=0)
        left.columnconfigure(0, weight=1)

        # Game screen placeholder
        self.canvas_label = ctk.CTkLabel(left, text="Loading...")
        self.canvas_label.grid(row=0, column=0, sticky="nsew")
        self.canvas_label.bind("<Button-1>", lambda _e: self._focus_game())

        # Speed controls under the screen
        controls = ctk.CTkFrame(left)
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        controls.columnconfigure((0, 1, 2), weight=1)
        self.speed_label = ctk.CTkLabel(controls, text="Speed 1.0x")
        self.speed_label.grid(row=0, column=0, padx=4)
        ctk.CTkButton(controls, text="Speed -", command=lambda: self._adjust_speed(1 / 1.5)).grid(row=0, column=1, padx=4)
        ctk.CTkButton(controls, text="Speed +", command=lambda: self._adjust_speed(1.5)).grid(row=0, column=2, padx=4)

        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(right)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        top_bar.columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(top_bar, text="Live", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w", padx=4)
        self.pause_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(top_bar, text="Pause updates", variable=self.pause_var, command=self._toggle_pause).grid(row=0, column=1, padx=6)
        ctk.CTkButton(top_bar, text="Apply", command=self._apply_edits).grid(row=0, column=2, padx=4)
        ctk.CTkButton(top_bar, text="Revert", command=self._revert_edits).grid(row=0, column=3, padx=4)

        self.tabs = ctk.CTkTabview(right, width=360)
        self.tabs.grid(row=1, column=0, sticky="nsew")

        self.player_tab = self.tabs.add("Player")
        self.party_tab = self.tabs.add("Party")
        self.inventory_tab = self.tabs.add("Inventory")
        self.battle_tab = self.tabs.add("Battle")

        self._build_player_tab()
        self._build_party_tab()
        self._build_inventory_tab()
        self._build_battle_tab()

        state_controls = ctk.CTkFrame(right)
        state_controls.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        for i in range(3):
            ctk.CTkButton(state_controls, text=f"Save {i+1}", command=lambda n=i+1: self._save_slot(n)).grid(row=0, column=i, padx=3)
        for i in range(3):
            ctk.CTkButton(state_controls, text=f"Load {i+1}", command=lambda n=i+1: self._load_slot(n)).grid(row=1, column=i, padx=3, pady=(4, 0))

        hint = (
            "Keys: WASD move, Z=A, X=B, C/Enter=Start, V/Space=Select. "
            "Use tabs to inspect/edit; Apply writes buffered changes."
        )
        self.hint_label = ctk.CTkLabel(right, text=hint, wraplength=320, anchor="w", justify="left")
        self.hint_label.grid(row=3, column=0, sticky="ew", pady=(6, 0))

    def _bind_keys(self):
        keymap = {
            "w": (WindowEvent.PRESS_ARROW_UP, WindowEvent.RELEASE_ARROW_UP),
            "s": (WindowEvent.PRESS_ARROW_DOWN, WindowEvent.RELEASE_ARROW_DOWN),
            "d": (WindowEvent.PRESS_ARROW_RIGHT, WindowEvent.RELEASE_ARROW_RIGHT),
            "a": (WindowEvent.PRESS_ARROW_LEFT, WindowEvent.RELEASE_ARROW_LEFT),
            "z": (WindowEvent.PRESS_BUTTON_A, WindowEvent.RELEASE_BUTTON_A),
            "x": (WindowEvent.PRESS_BUTTON_B, WindowEvent.RELEASE_BUTTON_B),
            "c": (WindowEvent.PRESS_BUTTON_START, WindowEvent.RELEASE_BUTTON_START),
            "v": (WindowEvent.PRESS_BUTTON_SELECT, WindowEvent.RELEASE_BUTTON_SELECT),
            "return": (WindowEvent.PRESS_BUTTON_START, WindowEvent.RELEASE_BUTTON_START),
            "space": (WindowEvent.PRESS_BUTTON_SELECT, WindowEvent.RELEASE_BUTTON_SELECT),
        }
        self.keymap = keymap
        self.held_keys: set[str] = set()
        for bind_key in ["w", "a", "s", "d", "z", "x", "c", "v", "Return", "space"]:
            self.bind(f"<KeyPress-{bind_key}>", self._on_key_press)
            self.bind(f"<KeyRelease-{bind_key}>", self._on_key_release)
        self.bind("<Escape>", lambda _e: self._focus_game())
        self.focus_set()

    def _focus_game(self):
        """Return keyboard focus to the main window so game controls work."""
        try:
            self.focus_set()
        except Exception:
            pass

    def _toggle_pause(self):
        self.paused = bool(self.pause_var.get())
        self.status_label.configure(text="Paused" if self.paused else "Live")

    # ------------------------------------------------------------------
    # Apply / Revert stubs
    # ------------------------------------------------------------------

    def _apply_edits(self):
        def _parse_int(text: str) -> int:
            t = (text or "").strip()
            if not t:
                raise ValueError("empty")
            return int(t, 0)

        supported_keys = [
            "player_name",
            "money",
            "mom_money",
            "casino_coins",
            "repel_steps",
            "on_bike_flag",
            "map_bank",
            "map_number",
            "player_x",
            "player_y",
        ]

        # Pull current UI values into the buffer so Apply works even while focused.
        self.edit_buffer["player_name"] = self.var_trainer_name.get()
        self.edit_buffer["money"] = self.var_money.get()
        self.edit_buffer["mom_money"] = self.var_mom_money.get()
        self.edit_buffer["casino_coins"] = self.var_casino.get()
        self.edit_buffer["repel_steps"] = self.var_repel.get()
        self.edit_buffer["on_bike_flag"] = bool(self.var_on_bike.get())
        self.edit_buffer["map_bank"] = self.var_map_bank.get()
        self.edit_buffer["map_number"] = self.var_map_no.get()
        self.edit_buffer["player_x"] = self.var_x.get()
        self.edit_buffer["player_y"] = self.var_y.get()

        # Apply supported edits.
        for key in supported_keys:
            if key not in self.edit_buffer:
                continue
            field = self.ram_catalog.get(key)
            if field is None:
                continue
            if key == "player_name":
                raw = encode_gsc_text(str(self.edit_buffer[key]), field.size)
                gml.write_field(self.write_mem, field, raw)
            elif key == "on_bike_flag":
                gml.write_field(self.write_mem, field, 1 if bool(self.edit_buffer[key]) else 0)
            else:
                gml.write_field(self.write_mem, field, _parse_int(str(self.edit_buffer[key])))

        # Party move edits (buffered as raw 4-byte move lists per slot).
        for slot in range(6):
            mkey = f"party[{slot}].moves"
            if mkey not in self.edit_buffer:
                continue
            field = self.ram_catalog.get(mkey)
            if field is None:
                continue
            raw = self.edit_buffer[mkey]
            if isinstance(raw, (bytes, bytearray)) and len(raw) == 4:
                gml.write_field(self.write_mem, field, bytes(raw))

        # Party species edits (buffered as int IDs per slot).
        for slot in range(6):
            skey = f"party[{slot}].species"
            if skey not in self.edit_buffer:
                continue
            field = self.ram_catalog.get(skey)
            if field is None:
                continue
            gml.write_field(self.write_mem, field, int(self.edit_buffer[skey]) & 0xFF)

        self.edit_buffer.clear()
        self.dirty = False

    def _revert_edits(self):
        self.edit_buffer.clear()
        self.dirty = False

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def _build_player_tab(self):
        frame = self.player_tab
        frame.columnconfigure(1, weight=1)

        def add_row(row, label, widget):
            ctk.CTkLabel(frame, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            widget.grid(row=row, column=1, sticky="ew", padx=4, pady=2)

        self.var_trainer_name = ctk.StringVar()
        self.entry_trainer_name = ctk.CTkEntry(frame, textvariable=self.var_trainer_name)
        self.entry_trainer_name.bind("<FocusIn>", lambda _e: self._begin_edit("player_name"))
        self.entry_trainer_name.bind("<FocusOut>", lambda _e: self._end_edit("player_name"))
        self.entry_trainer_name.bind("<Return>", lambda _e: (self._apply_edits(), self._focus_game()))
        add_row(0, "Trainer Name", self.entry_trainer_name)

        self.var_trainer_id = ctk.StringVar()
        add_row(1, "Trainer ID", ctk.CTkEntry(frame, textvariable=self.var_trainer_id))

        self.var_money = ctk.StringVar()
        self.entry_money = ctk.CTkEntry(frame, textvariable=self.var_money)
        self.entry_money.bind("<FocusIn>", lambda _e: self._begin_edit("money"))
        self.entry_money.bind("<FocusOut>", lambda _e: self._end_edit("money"))
        self.entry_money.bind("<Return>", lambda _e: (self._apply_edits(), self._focus_game()))
        add_row(2, "Money", self.entry_money)

        self.var_mom_money = ctk.StringVar()
        self.entry_mom_money = ctk.CTkEntry(frame, textvariable=self.var_mom_money)
        self.entry_mom_money.bind("<FocusIn>", lambda _e: self._begin_edit("mom_money"))
        self.entry_mom_money.bind("<FocusOut>", lambda _e: self._end_edit("mom_money"))
        self.entry_mom_money.bind("<Return>", lambda _e: (self._apply_edits(), self._focus_game()))
        add_row(3, "Mom Money", self.entry_mom_money)

        self.var_casino = ctk.StringVar()
        self.entry_casino = ctk.CTkEntry(frame, textvariable=self.var_casino)
        self.entry_casino.bind("<FocusIn>", lambda _e: self._begin_edit("casino_coins"))
        self.entry_casino.bind("<FocusOut>", lambda _e: self._end_edit("casino_coins"))
        self.entry_casino.bind("<Return>", lambda _e: (self._apply_edits(), self._focus_game()))
        add_row(4, "Casino Coins", self.entry_casino)

        self.var_repel = ctk.StringVar()
        self.entry_repel = ctk.CTkEntry(frame, textvariable=self.var_repel)
        self.entry_repel.bind("<FocusIn>", lambda _e: self._begin_edit("repel_steps"))
        self.entry_repel.bind("<FocusOut>", lambda _e: self._end_edit("repel_steps"))
        self.entry_repel.bind("<Return>", lambda _e: (self._apply_edits(), self._focus_game()))
        add_row(5, "Repel Steps", self.entry_repel)

        self.var_on_bike = ctk.BooleanVar()
        self.chk_on_bike = ctk.CTkCheckBox(frame, variable=self.var_on_bike, text="", command=lambda: self._mark_bool_edit("on_bike_flag", self.var_on_bike.get()))
        add_row(6, "On Bike", self.chk_on_bike)

        self.var_badge_johto = ctk.IntVar()
        self.var_badge_kanto = ctk.IntVar()
        badge_frame = ctk.CTkFrame(frame)
        badge_frame.grid(row=7, column=1, sticky="ew", padx=4, pady=2)
        ctk.CTkLabel(frame, text="Badges").grid(row=7, column=0, sticky="w", padx=4, pady=2)
        self.chk_johto = ctk.CTkCheckBox(badge_frame, text="Johto byte", variable=self.var_badge_johto)
        self.chk_kanto = ctk.CTkCheckBox(badge_frame, text="Kanto byte", variable=self.var_badge_kanto)
        self.chk_johto.grid(row=0, column=0, padx=2)
        self.chk_kanto.grid(row=0, column=1, padx=2)

        self.var_map_bank = ctk.StringVar()
        self.var_map_no = ctk.StringVar()
        self.entry_map_bank = ctk.CTkEntry(frame, textvariable=self.var_map_bank)
        self.entry_map_bank.bind("<FocusIn>", lambda _e: self._begin_edit("map_bank"))
        self.entry_map_bank.bind("<FocusOut>", lambda _e: self._end_edit("map_bank"))
        self.entry_map_bank.bind("<Return>", lambda _e: (self._apply_edits(), self._focus_game()))
        add_row(8, "Map Bank", self.entry_map_bank)

        self.entry_map_no = ctk.CTkEntry(frame, textvariable=self.var_map_no)
        self.entry_map_no.bind("<FocusIn>", lambda _e: self._begin_edit("map_number"))
        self.entry_map_no.bind("<FocusOut>", lambda _e: self._end_edit("map_number"))
        self.entry_map_no.bind("<Return>", lambda _e: (self._apply_edits(), self._focus_game()))
        add_row(9, "Map No", self.entry_map_no)

        self.var_x = ctk.StringVar()
        self.var_y = ctk.StringVar()
        self.entry_x = ctk.CTkEntry(frame, textvariable=self.var_x)
        self.entry_x.bind("<FocusIn>", lambda _e: self._begin_edit("player_x"))
        self.entry_x.bind("<FocusOut>", lambda _e: self._end_edit("player_x"))
        self.entry_x.bind("<Return>", lambda _e: (self._apply_edits(), self._focus_game()))
        add_row(10, "Player X", self.entry_x)

        self.entry_y = ctk.CTkEntry(frame, textvariable=self.var_y)
        self.entry_y.bind("<FocusIn>", lambda _e: self._begin_edit("player_y"))
        self.entry_y.bind("<FocusOut>", lambda _e: self._end_edit("player_y"))
        self.entry_y.bind("<Return>", lambda _e: (self._apply_edits(), self._focus_game()))
        add_row(11, "Player Y", self.entry_y)

        self.var_allow_danger = ctk.BooleanVar(value=False)
        add_row(12, "Unsafe writes", ctk.CTkCheckBox(frame, text="I know what I'm doing", variable=self.var_allow_danger))

    def _build_party_tab(self):
        frame = self.party_tab
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        top = ctk.CTkFrame(frame)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        top.columnconfigure(7, weight=1)

        self.var_party_count = ctk.StringVar()
        ctk.CTkLabel(top, text="Party Count").grid(row=0, column=0, padx=4)
        ctk.CTkEntry(top, width=50, textvariable=self.var_party_count).grid(row=0, column=1, padx=4)

        self.party_buttons = []
        for i in range(6):
            btn = ctk.CTkButton(top, text=f"Slot {i+1}", command=lambda n=i: self._set_active_party_slot(n))
            btn.grid(row=0, column=2 + i, padx=2)
            self.party_buttons.append(btn)

        detail = ctk.CTkFrame(frame)
        detail.grid(row=1, column=0, sticky="nsew")
        for col in range(2):
            detail.columnconfigure(col, weight=1)

        def add_row(r, label, widget, col=0):
            ctk.CTkLabel(detail, text=label).grid(row=r, column=col * 2, sticky="w", padx=4, pady=2)
            widget.grid(row=r, column=col * 2 + 1, sticky="ew", padx=4, pady=2)

        self.var_party_species = ctk.StringVar()
        self.var_party_species_choice = ctk.StringVar()
        self.var_party_level = ctk.StringVar()
        self.var_party_exp = ctk.StringVar()
        self.var_party_happiness = ctk.StringVar()
        self.var_party_pokerus = ctk.StringVar()
        self.var_party_item = ctk.StringVar()
        self.var_party_status = ctk.StringVar()
        self.var_party_hp = ctk.StringVar()
        self.var_party_hp_max = ctk.StringVar()
        self.var_party_pp = [ctk.StringVar() for _ in range(4)]

        self._species_choices = [names.format_species_choice(i) for i in range(1, 252)]
        self.species_combo = ctk.CTkComboBox(
            detail,
            values=self._species_choices,
            variable=self.var_party_species_choice,
            command=lambda choice: self._on_species_selected(choice),
        )
        add_row(0, "Species", self.species_combo)
        add_row(1, "Level", ctk.CTkEntry(detail, textvariable=self.var_party_level))
        add_row(2, "EXP", ctk.CTkEntry(detail, textvariable=self.var_party_exp))
        add_row(3, "Happiness", ctk.CTkEntry(detail, textvariable=self.var_party_happiness))
        add_row(4, "Pokerus", ctk.CTkEntry(detail, textvariable=self.var_party_pokerus))
        add_row(5, "Held Item", ctk.CTkEntry(detail, textvariable=self.var_party_item))
        add_row(6, "Status", ctk.CTkEntry(detail, textvariable=self.var_party_status))
        add_row(7, "HP", ctk.CTkEntry(detail, textvariable=self.var_party_hp))
        add_row(8, "Max HP", ctk.CTkEntry(detail, textvariable=self.var_party_hp_max))

        move_frame = ctk.CTkFrame(detail)
        move_frame.grid(row=0, column=2, rowspan=5, sticky="nsew", padx=4, pady=2)
        move_frame.columnconfigure(1, weight=1)
        ctk.CTkLabel(move_frame, text="Moves / PP").grid(row=0, column=0, columnspan=2, pady=(0, 4))
        self._move_choices = [names.format_choice(i) for i in range(1, 256)]
        self.move_combos = []
        for i in range(4):
            ctk.CTkLabel(move_frame, text=f"Move {i+1}").grid(row=1 + i, column=0, sticky="w", padx=4, pady=2)
            combo = ctk.CTkComboBox(
                move_frame,
                values=self._move_choices,
                command=lambda choice, idx=i: self._on_move_selected(idx, choice),
            )
            combo.grid(row=1 + i, column=1, sticky="ew", padx=4, pady=2)
            self.move_combos.append(combo)
            ctk.CTkEntry(move_frame, width=60, textvariable=self.var_party_pp[i]).grid(row=1 + i, column=2, sticky="ew", padx=4, pady=2)

        util_frame = ctk.CTkFrame(detail)
        util_frame.grid(row=6, column=2, sticky="ew", padx=4, pady=4)
        ctk.CTkButton(util_frame, text="Heal", command=self._heal_active_party).grid(row=0, column=0, padx=3)
        ctk.CTkButton(util_frame, text="Cure", command=self._cure_active_party).grid(row=0, column=1, padx=3)
        ctk.CTkButton(util_frame, text="Revive", command=self._revive_active_party).grid(row=0, column=2, padx=3)
        ctk.CTkButton(util_frame, text="Rare Candy +1", command=self._add_rare_candy).grid(row=0, column=3, padx=3)
        ctk.CTkButton(util_frame, text="Add Pokémon…", command=self._add_party_pokemon_dialog).grid(row=0, column=4, padx=3)
        ctk.CTkButton(util_frame, text="Delete Pokémon", command=self._delete_party_pokemon).grid(row=0, column=5, padx=3)

    # ------------------------------------------------------------------
    # Tab update helpers
    # ------------------------------------------------------------------

    def _set_active_party_slot(self, slot: int):
        self.active_party_slot = max(0, min(5, slot))
        for i, btn in enumerate(self.party_buttons):
            label = f"Slot {i+1}"
            if i == self.active_party_slot:
                label += " *"
            btn.configure(text=label)
        if self._last_live_snapshot:
            self._update_party_tab(self._last_live_snapshot)

    def _update_player_tab(self, live: dict[str, object]):
        # Name
        if "player_name" in self._editing_keys:
            pass
        elif "player_name" in self.edit_buffer:
            self.var_trainer_name.set(str(self.edit_buffer.get("player_name", "")))
        else:
            raw_name = live.get("player_name", b"")
            if isinstance(raw_name, (bytes, bytearray)):
                self.var_trainer_name.set(decode_gsc_text(raw_name))
            else:
                self.var_trainer_name.set(str(raw_name))

        # Trainer ID is read-only for now
        self.var_trainer_id.set(str(live.get("trainer_id", "")))

        # Numeric / flag fields
        def _set_entry(key: str, var: ctk.Variable, live_key: str | None = None):
            lk = live_key or key
            if key in self._editing_keys:
                return
            if key in self.edit_buffer:
                var.set(str(self.edit_buffer.get(key, "")))
                return
            var.set(str(live.get(lk, "")))

        _set_entry("money", self.var_money)
        _set_entry("mom_money", self.var_mom_money)
        _set_entry("casino_coins", self.var_casino)
        _set_entry("repel_steps", self.var_repel)
        _set_entry("map_bank", self.var_map_bank)
        _set_entry("map_number", self.var_map_no, live_key="map_number")
        _set_entry("player_x", self.var_x)
        _set_entry("player_y", self.var_y)

        if "on_bike_flag" not in self._editing_keys:
            if "on_bike_flag" in self.edit_buffer:
                self.var_on_bike.set(bool(self.edit_buffer.get("on_bike_flag")))
            else:
                self.var_on_bike.set(bool(live.get("on_bike_flag", False)))

    def _begin_edit(self, key: str):
        self._editing_keys.add(key)

    def _end_edit(self, key: str):
        self._editing_keys.discard(key)
        if key == "player_name":
            self.edit_buffer[key] = self.var_trainer_name.get()
            self.dirty = True
            return
        if key == "money":
            self.edit_buffer[key] = self.var_money.get()
            self.dirty = True
            return
        if key == "mom_money":
            self.edit_buffer[key] = self.var_mom_money.get()
            self.dirty = True
            return
        if key == "casino_coins":
            self.edit_buffer[key] = self.var_casino.get()
            self.dirty = True
            return
        if key == "repel_steps":
            self.edit_buffer[key] = self.var_repel.get()
            self.dirty = True
            return
        if key == "map_bank":
            self.edit_buffer[key] = self.var_map_bank.get()
            self.dirty = True
            return
        if key == "map_number":
            self.edit_buffer[key] = self.var_map_no.get()
            self.dirty = True
            return
        if key == "player_x":
            self.edit_buffer[key] = self.var_x.get()
            self.dirty = True
            return
        if key == "player_y":
            self.edit_buffer[key] = self.var_y.get()
            self.dirty = True
            return

    def _mark_bool_edit(self, key: str, value: bool):
        self.edit_buffer[key] = bool(value)
        self.dirty = True

    def _on_move_selected(self, move_index_0_to_3: int, choice: str):
        slot = self.active_party_slot
        key = f"party[{slot}].moves"
        try:
            move_id = names.parse_choice(choice)
        except Exception:
            return

        current = self._last_live_snapshot.get(key, b"\x00\x00\x00\x00")
        if key in self.edit_buffer and isinstance(self.edit_buffer[key], (bytes, bytearray)):
            current = self.edit_buffer[key]

        if not isinstance(current, (bytes, bytearray)):
            current = b"\x00\x00\x00\x00"
        b = bytearray(bytes(current[:4]).ljust(4, b"\x00"))
        b[move_index_0_to_3] = int(move_id) & 0xFF
        self.edit_buffer[key] = bytes(b)
        self.dirty = True

    def _on_species_selected(self, choice: str):
        slot = self.active_party_slot
        key = f"party[{slot}].species"
        try:
            species_id = names.parse_choice(choice)
        except Exception:
            return
        self.edit_buffer[key] = int(species_id) & 0xFF
        self.dirty = True

    def _add_rare_candy(self):
        """Add 1 Rare Candy to the bag (safer than direct level edits)."""
        RARE_CANDY_ID = 0x20
        MAX_QTY = 99

        bag_len = (gml.BAG_ITEMS_END_OF_LIST - gml.BAG_ITEMS_START) + 1
        data = bytearray(self.read_mem(gml.BAG_ITEMS_START, bag_len))

        term_index = None
        found_qty_index = None
        for i in range(0, len(data) - 1, 2):
            item_id = data[i]
            if item_id == 0xFF:
                term_index = i
                break
            if item_id == RARE_CANDY_ID:
                found_qty_index = i + 1
                break

        if found_qty_index is not None:
            data[found_qty_index] = min(MAX_QTY, int(data[found_qty_index]) + 1)
            self.write_mem(gml.BAG_ITEMS_START, bytes(data))
            self.dirty = True
            return

        if term_index is None:
            return
        if term_index + 2 >= len(data):
            return

        data[term_index] = RARE_CANDY_ID
        data[term_index + 1] = 1
        data[term_index + 2] = 0xFF
        if term_index + 3 < len(data):
            data[term_index + 3] = 0x00

        try:
            count = int(self.read_mem(gml.BAG_ITEM_COUNT, 1)[0])
            self.write_mem(gml.BAG_ITEM_COUNT, bytes(((count + 1) & 0xFF,)))
        except Exception:
            pass

        self.write_mem(gml.BAG_ITEMS_START, bytes(data))
        self.dirty = True

    def _add_party_pokemon_dialog(self):
        """Prompt for species + level using a combobox, then append to party."""
        try:
            dlg = ctk.CTkToplevel(self)
            dlg.title("Add Pokémon")
            dlg.resizable(False, False)
            dlg.grab_set()

            dlg.columnconfigure(1, weight=1)

            ctk.CTkLabel(dlg, text="Species").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
            species_var = ctk.StringVar(value=names.format_species_choice(1))
            species_values = getattr(self, "_species_choices", [names.format_species_choice(i) for i in range(1, 252)])
            ctk.CTkComboBox(dlg, values=species_values, variable=species_var).grid(
                row=0, column=1, sticky="ew", padx=10, pady=(10, 6)
            )

            ctk.CTkLabel(dlg, text="Level").grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))
            level_var = ctk.StringVar(value="5")
            level_entry = ctk.CTkEntry(dlg, textvariable=level_var)
            level_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=(0, 6))

            result: dict[str, int] = {}

            def on_ok():
                try:
                    sid = names.parse_choice(species_var.get())
                    lvl = int((level_var.get() or "").strip() or "5", 0)
                    lvl = max(1, min(100, lvl))
                    if not (1 <= sid <= 251):
                        raise ValueError
                    result["species_id"] = sid
                    result["level"] = lvl
                    dlg.destroy()
                except Exception:
                    messagebox.showerror("Add Pokémon", "Please choose a valid species and level (1-100).")

            def on_cancel():
                dlg.destroy()

            btns = ctk.CTkFrame(dlg)
            btns.grid(row=2, column=0, columnspan=2, sticky="e", padx=10, pady=(6, 10))
            ctk.CTkButton(btns, text="Cancel", command=on_cancel).grid(row=0, column=0, padx=(0, 6))
            ctk.CTkButton(btns, text="Add", command=on_ok).grid(row=0, column=1)

            level_entry.focus_set()
            dlg.bind("<Return>", lambda _e: on_ok())
            dlg.bind("<Escape>", lambda _e: on_cancel())

            self.wait_window(dlg)
            if not result:
                return

            species_id = int(result["species_id"])
            level = int(result["level"])
            self._append_party_pokemon(species_id=species_id, level=level)
            self.status_label.configure(text=f"Added {names.species_name(species_id)} Lv{level}")
        except Exception as exc:  # noqa: BLE001
            self.status_label.configure(text=f"Add Pokémon failed: {exc}")

    def _append_party_pokemon(self, species_id: int, level: int):
        """Write a new party slot with minimal sane defaults."""
        count = int(self.read_mem(gml.PARTY_COUNT, 1)[0])
        if count >= 6:
            raise ValueError("Party is full")
        slot = count
        new_count = count + 1

        # Update party count
        self.write_mem(gml.PARTY_COUNT, bytes((new_count & 0xFF,)))

        # Update species list (DA23..DA28) + terminator (DA29)
        species_list = bytearray(self.read_mem(gml.PARTY_SPECIES_LIST_START, 7))
        if len(species_list) < 7:
            species_list = bytearray(b"\x00" * 7)
        species_list[slot] = species_id & 0xFF
        for i in range(new_count, 6):
            species_list[i] = 0
        species_list[6] = 0xFF
        self.write_mem(gml.PARTY_SPECIES_LIST_START, bytes(species_list))

        base = gml.party_mon_base(slot)

        def w8(off: int, v: int):
            self.write_mem(base + off, bytes((v & 0xFF,)))

        def w16be(off: int, v: int):
            self.write_mem(base + off, bytes(((v >> 8) & 0xFF, v & 0xFF)))

        def w24le(off: int, v: int):
            self.write_mem(base + off, bytes((v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF)))

        # Core identity
        w8(gml.PARTY_MON_SPECIES_OFF, species_id)
        w8(gml.PARTY_MON_HELD_ITEM_OFF, 0)

        # Moves / PP (best-effort: Gold/Silver level-up moves; safe fallback when offline)
        move_ids, pp_vals = self._suggest_moves_for_species_level(species_id, int(level))
        move_ids = (list(move_ids) + [0, 0, 0, 0])[:4]
        pp_vals = (list(pp_vals) + [0, 0, 0, 0])[:4]
        self.write_mem(base + gml.PARTY_MON_MOVES_OFF, bytes((int(m) & 0xFF for m in move_ids)))
        self.write_mem(base + gml.PARTY_MON_PP_OFF, bytes((int(p) & 0xFF for p in pp_vals)))

        # OT/mon ID: 0 is okay for now
        w16be(gml.PARTY_MON_ID_OFF, 0)

        # EXP: rough placeholder (keeps monotonic growth-ish)
        exp = min(0xFFFFFF, int(level) ** 3)
        w24le(gml.PARTY_MON_EXP_OFF, exp)

        # EVs (10 bytes from HP_EV..SPC_EV): zero
        self.write_mem(base + gml.PARTY_MON_HP_EV_OFF, b"\x00" * 10)

        # IVs: moderate
        w8(gml.PARTY_MON_IV_AD_OFF, 0x88)
        w8(gml.PARTY_MON_IV_SS_OFF, 0x88)

        # Happiness / Pokerus / caught data
        w8(gml.PARTY_MON_HAPPINESS_OFF, 70)
        w8(gml.PARTY_MON_POKERUS_OFF, 0)
        self.write_mem(base + gml.PARTY_MON_CAUGHT_DATA_OFF, b"\x00\x00")

        # Level / status
        w8(gml.PARTY_MON_LEVEL_OFF, int(level))
        w16be(gml.PARTY_MON_STATUS_OFF, 0)

        # Basic stats (very rough, but stable)
        max_hp = max(12, 10 + int(level) * 3)
        hp = max_hp
        atk = max(5, 5 + int(level) * 2)
        defense = max(5, 5 + int(level) * 2)
        spd = max(5, 5 + int(level) * 2)
        spatk = max(5, 5 + int(level) * 2)
        spdef = max(5, 5 + int(level) * 2)

        w16be(gml.PARTY_MON_HP_OFF, hp)
        w16be(gml.PARTY_MON_MAX_HP_OFF, max_hp)
        w16be(gml.PARTY_MON_ATK_OFF, atk)
        w16be(gml.PARTY_MON_DEF_OFF, defense)
        w16be(gml.PARTY_MON_SPD_OFF, spd)
        w16be(gml.PARTY_MON_SPATK_OFF, spatk)
        w16be(gml.PARTY_MON_SPDEF_OFF, spdef)

        # Populate OT name + nickname so in-game menus don't show '?'.
        try:
            t_start, t_end = gml.TRAINER_NAME
            trainer_raw = self.read_mem(t_start, (t_end - t_start) + 1)
            trainer_name = decode_gsc_text(trainer_raw) or "TRAINER"
        except Exception:
            trainer_name = "TRAINER"

        nickname = names.species_name(species_id).upper() or "POKEMON"
        self.write_mem(gml.party_ot_name_addr(slot), encode_gsc_text(trainer_name.upper(), gml.PARTY_NAME_LEN))
        self.write_mem(gml.party_nickname_addr(slot), encode_gsc_text(nickname, gml.PARTY_NAME_LEN))

        self.active_party_slot = slot
        self.dirty = True

    def _update_party_tab(self, live: dict[str, object]):
        self.var_party_count.set(str(live.get("party_count", "")))
        for i, btn in enumerate(self.party_buttons):
            label = f"Slot {i+1}"
            if i == self.active_party_slot:
                label += " *"
            btn.configure(text=label)

        slot = self.active_party_slot
        prefix = f"party[{slot}]"
        species_key = f"{prefix}.species"
        if species_key in self.edit_buffer:
            species_id = _to_int(self.edit_buffer.get(species_key, 0), 0)
        else:
            species_id = _to_int(live.get(species_key, 0), 0)
        self.var_party_species.set(f"{names.species_name(species_id)} ({species_id})")
        try:
            focused = self.focus_get()
            if focused is None or focused != self.species_combo:
                if species_id > 0:
                    self.var_party_species_choice.set(names.format_species_choice(species_id))
        except Exception:
            pass
        self.var_party_level.set(str(live.get(f"{prefix}.level", "")))
        self.var_party_exp.set(str(live.get(f"{prefix}.exp", "")))
        self.var_party_happiness.set(str(live.get(f"{prefix}.happiness", "")))
        self.var_party_pokerus.set(str(live.get(f"{prefix}.pokerus", "")))
        item_id = _to_int(live.get(f"{prefix}.item", 0), 0)
        self.var_party_item.set(f"{names.item_name(item_id)} ({item_id})")
        self.var_party_status.set(str(live.get(f"{prefix}.status", "")))
        self.var_party_hp.set(str(live.get(f"{prefix}.hp", "")))
        self.var_party_hp_max.set(str(live.get(f"{prefix}.max_hp", "")))

        moves_raw = live.get(f"{prefix}.moves", b"") or b""
        if isinstance(moves_raw, (bytes, bytearray)):
            move_ids = list(moves_raw[:4])
        else:
            move_ids = [0, 0, 0, 0]

        pps_raw = live.get(f"{prefix}.pp", b"") or b""
        if isinstance(pps_raw, (bytes, bytearray)):
            pp_ids = list(pps_raw[:4])
        else:
            pp_ids = [0, 0, 0, 0]

        for i in range(4):
            self.var_party_pp[i].set(str(pp_ids[i] if i < len(pp_ids) else ""))
            try:
                # Don't clobber if user is actively interacting with the dropdown
                focused = self.focus_get()
                if focused is not None and focused == self.move_combos[i]:
                    continue
            except Exception:
                pass
            mid = int(move_ids[i] if i < len(move_ids) else 0)
            if mid <= 0:
                self.move_combos[i].set("")
            else:
                self.move_combos[i].set(names.format_choice(mid))

    def _update_inventory_tab(self, live: dict[str, object]):
        # Avoid clobbering while the user is scrolling/selecting in the inventory view.
        try:
            if self.focus_get() == self.inv_text:
                return
        except Exception:
            pass

        items = self._read_bag_items()
        header = [
            f"Bag items: {len(items)}",
            "",
        ]
        lines = [f"{idx+1:02d}. {names.item_name(item_id)} ({item_id}) x{qty}" for idx, (item_id, qty) in enumerate(items)]

        self.inv_text.configure(state="normal")
        self.inv_text.delete("1.0", "end")
        self.inv_text.insert("1.0", "\n".join(header + (lines or ["(empty)"])))
        self.inv_text.configure(state="disabled")

    def _update_battle_tab(self, live: dict[str, object]):
        lines = [
            f"Battle type: {live.get('battle_type', '-')}",
            f"Wild species: {live.get('wild_species', '-')}",
            f"Wild level: {live.get('wild_level', '-')}",
        ]
        self.battle_text.configure(state="normal")
        self.battle_text.delete("1.0", "end")
        self.battle_text.insert("1.0", "\n".join(lines))
        self.battle_text.configure(state="disabled")

    def _build_inventory_tab(self):
        frame = self.inventory_tab
        frame.rowconfigure(0, weight=1)
        frame.rowconfigure(1, weight=0)
        frame.columnconfigure(0, weight=1)

        self.inv_text = ctk.CTkTextbox(frame, width=320)
        self.inv_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.inv_text.insert("1.0", "Bag items will appear here.")
        self.inv_text.configure(state="disabled")

        controls = ctk.CTkFrame(frame)
        controls.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
        controls.columnconfigure(1, weight=1)

        ctk.CTkLabel(controls, text="Item").grid(row=0, column=0, padx=(6, 4), pady=6, sticky="w")
        self.inv_item_var = ctk.StringVar(value=names.format_item_choice(1))
        self.inv_item_combo = ctk.CTkComboBox(controls, values=self._inv_item_choices, variable=self.inv_item_var)
        self.inv_item_combo.grid(row=0, column=1, padx=4, pady=6, sticky="ew")

        ctk.CTkLabel(controls, text="Qty").grid(row=0, column=2, padx=(10, 4), pady=6, sticky="w")
        self.inv_qty_var = ctk.StringVar(value="1")
        self.inv_qty_entry = ctk.CTkEntry(controls, width=70, textvariable=self.inv_qty_var)
        self.inv_qty_entry.grid(row=0, column=3, padx=(0, 6), pady=6, sticky="e")

        btns = ctk.CTkFrame(controls)
        btns.grid(row=1, column=0, columnspan=4, sticky="ew", padx=6, pady=(0, 6))
        ctk.CTkButton(btns, text="Add / Set Qty", command=self._inventory_add_or_set).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(btns, text="Remove", command=self._inventory_remove).grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(btns, text="Refresh", command=self._inventory_refresh).grid(row=0, column=2)

    def _read_bag_items(self) -> list[tuple[int, int]]:
        """Read the bag items list (pairs of item_id, qty) terminated by 0xFF."""
        total_len = (gml.BAG_ITEMS_END_OF_LIST - gml.BAG_ITEMS_START) + 1
        blob = self.read_mem(gml.BAG_ITEMS_START, int(total_len))
        out: list[tuple[int, int]] = []
        i = 0
        while i < len(blob):
            item_id = blob[i]
            if item_id == 0xFF:
                break
            if i + 1 >= len(blob):
                break
            qty = blob[i + 1]
            if item_id != 0:
                out.append((int(item_id), int(qty)))
            i += 2
        return out

    def _write_bag_items(self, items: list[tuple[int, int]]):
        """Write bag items list, clamped to available space; updates BAG_ITEM_COUNT."""
        MAX_QTY = 99
        total_len = (gml.BAG_ITEMS_END_OF_LIST - gml.BAG_ITEMS_START) + 1
        max_slots = max(0, (int(total_len) - 1) // 2)

        # Normalize and clamp.
        normalized: list[tuple[int, int]] = []
        for item_id, qty in items:
            iid = int(item_id) & 0xFF
            if iid in (0, 0xFF):
                continue
            q = max(1, min(MAX_QTY, int(qty)))
            normalized.append((iid, q))

        normalized = normalized[:max_slots]

        data = bytearray(b"\x00" * int(total_len))
        pos = 0
        for iid, q in normalized:
            if pos + 2 > len(data):
                break
            data[pos] = iid & 0xFF
            data[pos + 1] = q & 0xFF
            pos += 2
        if pos < len(data):
            data[pos] = 0xFF

        self.write_mem(gml.BAG_ITEMS_START, bytes(data))
        self.write_mem(gml.BAG_ITEM_COUNT, bytes((len(normalized) & 0xFF,)))

    def _inventory_refresh(self):
        try:
            self._update_inventory_tab(self._last_live_snapshot or {})
        except Exception:
            pass

    def _inventory_add_or_set(self):
        try:
            item_id = names.parse_choice(self.inv_item_var.get())
            if not (1 <= item_id <= 255):
                raise ValueError
            qty = int((self.inv_qty_var.get() or "").strip() or "1", 0)
            qty = max(1, min(99, qty))

            items = self._read_bag_items()
            found = False
            new_items: list[tuple[int, int]] = []
            for iid, q in items:
                if iid == item_id:
                    new_items.append((iid, qty))
                    found = True
                else:
                    new_items.append((iid, q))
            if not found:
                new_items.append((item_id, qty))

            self._write_bag_items(new_items)
            self.dirty = True
            self._inventory_refresh()
            self.status_label.configure(text=f"Set {names.item_name(item_id)} x{qty}")
        except Exception as exc:  # noqa: BLE001
            self.status_label.configure(text=f"Inventory update failed: {exc}")

    def _inventory_remove(self):
        try:
            item_id = names.parse_choice(self.inv_item_var.get())
            items = [(iid, q) for (iid, q) in self._read_bag_items() if iid != item_id]
            self._write_bag_items(items)
            self.dirty = True
            self._inventory_refresh()
            self.status_label.configure(text=f"Removed {names.item_name(item_id)}")
        except Exception as exc:  # noqa: BLE001
            self.status_label.configure(text=f"Inventory remove failed: {exc}")

    def _build_battle_tab(self):
        frame = self.battle_tab
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.battle_text = ctk.CTkTextbox(frame, width=320)
        self.battle_text.grid(row=0, column=0, sticky="nsew")
        self.battle_text.insert("1.0", "Battle view (read-only)")
        self.battle_text.configure(state="disabled")

    def _on_key_press(self, event):
        focused = self.focus_get()
        if focused is not None:
            try:
                if focused.winfo_class() in ("Entry", "TEntry", "Text"):
                    return
            except Exception:
                pass
        key = event.keysym.lower()
        if key in self.keymap and key not in self.held_keys:
            press, _ = self.keymap[key]
            self.pyboy.send_input(press)
            self.held_keys.add(key)

    def _on_key_release(self, event):
        focused = self.focus_get()
        if focused is not None:
            try:
                if focused.winfo_class() in ("Entry", "TEntry", "Text"):
                    return
            except Exception:
                pass
        key = event.keysym.lower()
        if key in self.keymap and key in self.held_keys:
            _, release = self.keymap[key]
            self.pyboy.send_input(release)
            self.held_keys.remove(key)

    # ------------------------------------------------------------------
    # Party utilities
    # ------------------------------------------------------------------

    def _heal_active_party(self):
        slot = self.active_party_slot
        base = gml.party_mon_base(slot)
        hp_field = gml.MemField("hp", base + gml.PARTY_MON_HP_OFF, 2, gml.Encoding.U16_BE)
        max_field = gml.MemField("max_hp", base + gml.PARTY_MON_MAX_HP_OFF, 2, gml.Encoding.U16_BE)
        max_hp = gml.read_field(self.read_mem, max_field)
        gml.write_field(self.write_mem, hp_field, max_hp)
        status_field = gml.MemField("status", base + gml.PARTY_MON_STATUS_OFF, 2, gml.Encoding.U16_BE)
        gml.write_field(self.write_mem, status_field, 0)
        self.dirty = True

    def _cure_active_party(self):
        slot = self.active_party_slot
        base = gml.party_mon_base(slot)
        status_field = gml.MemField("status", base + gml.PARTY_MON_STATUS_OFF, 2, gml.Encoding.U16_BE)
        gml.write_field(self.write_mem, status_field, 0)
        self.dirty = True

    def _revive_active_party(self):
        slot = self.active_party_slot
        base = gml.party_mon_base(slot)
        max_field = gml.MemField("max_hp", base + gml.PARTY_MON_MAX_HP_OFF, 2, gml.Encoding.U16_BE)
        max_hp = int(gml.read_field(self.read_mem, max_field))
        hp_field = gml.MemField("hp", base + gml.PARTY_MON_HP_OFF, 2, gml.Encoding.U16_BE)
        gml.write_field(self.write_mem, hp_field, max(1, max_hp // 2))
        status_field = gml.MemField("status", base + gml.PARTY_MON_STATUS_OFF, 2, gml.Encoding.U16_BE)
        gml.write_field(self.write_mem, status_field, 0)
        self.dirty = True

    def _delete_party_pokemon(self):
        count = int(self.read_mem(gml.PARTY_COUNT, 1)[0])
        if count <= 0:
            self.status_label.configure(text="Party is empty")
            return

        slot = int(self.active_party_slot)
        if slot >= count:
            self.status_label.configure(text=f"Slot {slot + 1} is empty")
            return

        if not messagebox.askyesno("Delete Pokémon", f"Delete party Pokémon in slot {slot + 1}?"):
            return

        old_count = count
        new_count = old_count - 1

        # Shift species list down for the removed slot.
        species_list = bytearray(self.read_mem(gml.PARTY_SPECIES_LIST_START, 7))
        if len(species_list) < 7:
            species_list = bytearray(b"\x00" * 7)
        species = list(species_list[:6])
        for i in range(slot, old_count - 1):
            species[i] = species[i + 1]
        if old_count - 1 < 6:
            species[old_count - 1] = 0
        for i in range(new_count, 6):
            species[i] = 0
        species_list[:6] = bytes(species)
        species_list[6] = 0xFF
        self.write_mem(gml.PARTY_SPECIES_LIST_START, bytes(species_list))

        # Shift party mon structs + names down.
        for i in range(slot, old_count - 1):
            src_struct = self.read_mem(gml.party_mon_base(i + 1), gml.PARTY_MON_STRUCT_SIZE)
            self.write_mem(gml.party_mon_base(i), src_struct)

            src_ot = self.read_mem(gml.party_ot_name_addr(i + 1), gml.PARTY_NAME_LEN)
            self.write_mem(gml.party_ot_name_addr(i), src_ot)

            src_nick = self.read_mem(gml.party_nickname_addr(i + 1), gml.PARTY_NAME_LEN)
            self.write_mem(gml.party_nickname_addr(i), src_nick)

        # Clear the last slot (now empty).
        last_slot = old_count - 1
        self.write_mem(gml.party_mon_base(last_slot), b"\x00" * gml.PARTY_MON_STRUCT_SIZE)
        self.write_mem(gml.party_ot_name_addr(last_slot), encode_gsc_text("", gml.PARTY_NAME_LEN))
        self.write_mem(gml.party_nickname_addr(last_slot), encode_gsc_text("", gml.PARTY_NAME_LEN))

        # Update party count.
        self.write_mem(gml.PARTY_COUNT, bytes((new_count & 0xFF,)))

        # Any buffered party edits are now misaligned; drop them.
        self.edit_buffer = {k: v for (k, v) in self.edit_buffer.items() if not k.startswith("party[")}
        self._editing_keys = {k for k in self._editing_keys if not k.startswith("party[")}

        self.active_party_slot = max(0, min(slot, new_count - 1 if new_count > 0 else 0))
        self.dirty = True

        # Refresh immediately so the UI matches the shifted data.
        try:
            self._refresh_memory_panel()
        except Exception:
            pass
        self.status_label.configure(text=f"Deleted party slot {slot + 1}")

    def _adjust_speed(self, mult: float):
        self.speed = clamp_speed(self.speed, mult)
        self.pyboy.set_emulation_speed(self.speed)
        self.speed_label.configure(text=f"Speed {self.speed:.2f}x")

    def _save_slot(self, slot: int):
        try:
            STATE_DIR.mkdir(exist_ok=True)
            path = STATE_DIR / f"slot{slot}.state"
            with open(path, "wb") as f:
                self.pyboy.save_state(f)
            print(f"Saved state {slot} -> {path}")
        except Exception as exc:  # noqa: BLE001
            print(f"Save {slot} failed: {exc}")

    def _load_slot(self, slot: int):
        path = STATE_DIR / f"slot{slot}.state"
        if not path.exists():
            print(f"No save in slot {slot} ({path})")
            return
        try:
            with open(path, "rb") as f:
                self.pyboy.load_state(f)
            print(f"Loaded state {slot} <- {path}")
        except Exception as exc:  # noqa: BLE001
            print(f"Load {slot} failed: {exc}")

    def _loop(self):
        if not self.running:
            return

        try:
            if not self.paused:
                self.speed_accum += self.speed
                steps = 0
                while self.speed_accum >= 1.0:
                    if not self.pyboy.tick():
                        self.safe_destroy()
                        return
                    self.speed_accum -= 1.0
                    steps += 1

                # If running slower than real time (<1x), only tick when we accumulate enough.
                if steps == 0:
                    if self.running:
                        self.after(1, self._loop)
                    return

                self._refresh_screen()
                now = time.time()
                if now - self.last_mem_refresh > 0.5:
                    self._refresh_memory_panel()
                    self.last_mem_refresh = now
            else:
                # Even when paused, keep UI responsive.
                now = time.time()
                if now - self.last_mem_refresh > 1.0:
                    self._refresh_memory_panel()
                    self.last_mem_refresh = now
        except KeyboardInterrupt:
            self.safe_destroy()
            return
        except Exception:
            self.safe_destroy()
            raise

        if self.running:
            # Keep the loop hot; 1ms delay is enough for Tk to process paint events without feeling sluggish.
            self.after(1, self._loop)

    def _refresh_screen(self):
        img = self.pyboy.screen.image
        scale = 3
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        if not self.running:
            return
        # Use CTkImage to avoid DPI scaling warnings on high-DPI displays.
        self.ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
        self.canvas_label.configure(image=self.ctk_image, text="")
        self.update_idletasks()

    def _refresh_memory_panel(self):
        # Live snapshot of core fields to feed tabs.
        live = gml.snapshot_ram(self.read_mem, keys=[
            "player_name","trainer_id","player_x","player_y","map_bank","map_number",
            "money","mom_money","casino_coins","repel_steps","on_bike_flag","johto_badges",
            "kanto_badges","party_count","battle_type","wild_species","wild_level",
        ])
        # Party summary (first slot for detail)
        party_keys = []
        for i in range(6):
            party_keys.extend([
                f"party[{i}].species", f"party[{i}].level", f"party[{i}].hp", f"party[{i}].max_hp",
                f"party[{i}].status", f"party[{i}].item", f"party[{i}].moves", f"party[{i}].pp",
                f"party[{i}].exp", f"party[{i}].happiness", f"party[{i}].pokerus",
            ])
        party_snap = gml.snapshot_ram(self.read_mem, keys=party_keys)
        live.update(party_snap)
        self._last_live_snapshot = live

        self._update_player_tab(live)
        self._update_party_tab(live)
        self._update_inventory_tab(live)
        self._update_battle_tab(live)

        # Status/dirty indicator
        self.status_label.configure(text="Paused" if self.pause_var.get() else "Live")
        if self.dirty:
            self.status_label.configure(text=self.status_label.cget("text") + " *dirty*")

    def safe_destroy(self):
        if self._destroying:
            return
        self._destroying = True
        self.running = False

        # Save persistent state on shutdown.
        try:
            STATE_DIR.mkdir(exist_ok=True)
            with open(PERSIST_STATE, "wb") as f:
                self.pyboy.save_state(f)
            print(f"Saved persistent state to {PERSIST_STATE}")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to save persistent state: {exc}")

        try:
            self.pyboy.stop(save=False)
        except Exception:
            pass
        try:
            if self.winfo_exists():
                self.after(0, super().destroy)
        except Exception:
            pass

    def destroy(self):
        # Override to ensure safe destruction path is always used.
        self.safe_destroy()


def main():
    app = EmulatorApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.safe_destroy()


if __name__ == "__main__":
    main()
