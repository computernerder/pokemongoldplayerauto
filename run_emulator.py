from pathlib import Path
import time

import keyboard
from pyboy import PyBoy
from pyboy.utils import WindowEvent

import gsc_memory_lib as gml


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


def clamp_speed(current: float, mult: float) -> float:
    return max(MIN_SPEED, min(MAX_SPEED, current * mult))


def apply_speed(pyboy: PyBoy, current: float, mult: float) -> float:
    new_speed = clamp_speed(current, mult)
    pyboy.set_emulation_speed(new_speed)
    return new_speed


def save_state_slot(pyboy: PyBoy, slot: int, state_dir: Path = STATE_DIR) -> Path:
    state_dir.mkdir(exist_ok=True)
    path = state_dir / f"slot{slot}.state"
    with open(path, "wb") as f:
        pyboy.save_state(f)
    return path


def load_state_slot(pyboy: PyBoy, slot: int, state_dir: Path = STATE_DIR) -> Path:
    path = state_dir / f"slot{slot}.state"
    if not path.exists():
        raise FileNotFoundError(f"No save in slot {slot} ({path})")
    with open(path, "rb") as f:
        pyboy.load_state(f)
    return path


def create_pyboy(window: str = "SDL2", scale: int = 3, debug: bool = False) -> PyBoy:
    # PyBoy 2.6.x does not expose savefile kwarg; we handle persistence via save_state/load_state instead.
    return PyBoy(str(ROM_PATH), window=window, scale=scale, debug=debug)


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


def print_memory_panel(memory, watch_keys=DEFAULT_WATCH_KEYS) -> None:
    read_mem = _make_read_mem(memory)
    cat = gml.build_ram_catalog(include_party=False)
    lines = ["=== Memory Panel ==="]
    for key in watch_keys:
        field = cat.get(key)
        if field is None:
            lines.append(f"{key:<12} <missing field>")
            continue
        try:
            val = gml.read_field(read_mem, field)
            lines.append(f"{key:<12} @{field.addr:04X} = {_fmt_value(val)}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"{key:<12} @{field.addr:04X} = <err {exc}>")
    print("\n".join(lines))


def _parse_bytes(s: str) -> bytes:
    # Accept space/comma separated hex pairs, or plain hex string.
    cleaned = s.replace(",", " ").replace("0x", " ")
    parts = cleaned.split()
    if len(parts) == 0:
        return bytes()
    if len(parts) == 1:
        # Maybe a compact hex string with no spaces
        hex_str = parts[0]
        if len(hex_str) % 2 != 0:
            raise ValueError("Byte string hex must have even length")
        return bytes.fromhex(hex_str)
    return bytes(int(p, 16) for p in parts)


def prompt_memory_edit(memory) -> None:
    cat = gml.build_ram_catalog(include_party=True)
    read_mem = _make_read_mem(memory)
    write_mem = _make_write_mem(memory)

    try:
        raw_target = input("Field key (e.g., player_x or party[0].level) or hex addr (e.g., D20D): ").strip()
        if not raw_target:
            return

        if raw_target in cat:
            field = cat[raw_target]
            raw_val = input(f"Value for {field.key} (enc {field.enc}): ").strip()
            if field.enc in {gml.Encoding.U8, gml.Encoding.U16_LE, gml.Encoding.U16_BE, gml.Encoding.U24_LE, gml.Encoding.U24_BCD}:
                val = int(raw_val, 0)
            else:
                val = _parse_bytes(raw_val)
            gml.write_field(write_mem, field, val)
            new_val = gml.read_field(read_mem, field)
            print(f"Wrote {field.key} @{field.addr:04X} -> {_fmt_value(new_val)}")
            return

        # Fallback: treat as raw address edit (single byte)
        addr = int(raw_target.lower().replace("0x", ""), 16)
        raw_val = input("Value (0-255 dec or hex like 0xFF): ").strip()
        val = int(raw_val, 0)
        val = max(0, min(255, val))
        memory[addr] = val
        print(f"Wrote 0x{val:02X} to 0x{addr:04X}")
    except Exception as exc:  # noqa: BLE001
        print(f"Edit failed: {exc}")


def main() -> None:
    if not ROM_PATH.exists():
        raise FileNotFoundError(f"ROM not found at {ROM_PATH}")

    pyboy = create_pyboy(window="SDL2", scale=3, debug=False)

    # Load persistent state if present (fallback because savefile kwarg is unavailable in PyBoy 2.6.x).
    if PERSIST_STATE.exists():
        try:
            with open(PERSIST_STATE, "rb") as f:
                pyboy.load_state(f)
            print(f"Loaded persistent state from {PERSIST_STATE}")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to load persistent state: {exc}")

    # 1.0 = normal speed. Raise to fast-forward; 0 = unlimited (can be unstable visually).
    speed = 1.0
    pyboy.set_emulation_speed(speed)

    STATE_DIR.mkdir(exist_ok=True)

    # Keyboard mapping (press/release) for manual play.
    keymap = {
        "w": (WindowEvent.PRESS_ARROW_UP, WindowEvent.RELEASE_ARROW_UP),
        "s": (WindowEvent.PRESS_ARROW_DOWN, WindowEvent.RELEASE_ARROW_DOWN),
        "d": (WindowEvent.PRESS_ARROW_RIGHT, WindowEvent.RELEASE_ARROW_RIGHT),
        "a": (WindowEvent.PRESS_ARROW_LEFT, WindowEvent.RELEASE_ARROW_LEFT),
        "z": (WindowEvent.PRESS_BUTTON_A, WindowEvent.RELEASE_BUTTON_A),
        "x": (WindowEvent.PRESS_BUTTON_B, WindowEvent.RELEASE_BUTTON_B),
        "c": (WindowEvent.PRESS_BUTTON_START, WindowEvent.RELEASE_BUTTON_START),
        "v": (WindowEvent.PRESS_BUTTON_SELECT, WindowEvent.RELEASE_BUTTON_SELECT),
        "enter": (WindowEvent.PRESS_BUTTON_START, WindowEvent.RELEASE_BUTTON_START),
        "space": (WindowEvent.PRESS_BUTTON_SELECT, WindowEvent.RELEASE_BUTTON_SELECT),
    }

    held_keys = set()

    # One-shot controls (edge-triggered) using function keys to avoid symbol/shift ambiguity.
    control_keys = {
        "f6": "speed_up",
        "f5": "speed_down",
        "f1": "save_1",
        "f2": "save_2",
        "f3": "save_3",
        "f7": "load_1",
        "f8": "load_2",
        "f9": "load_3",
        "f10": "mem_edit",
    }
    held_controls = set()

    def adjust_speed(mult: float) -> None:
        nonlocal speed
        speed = apply_speed(pyboy, speed, mult)
        print(f"Speed set to {speed:.2f}x")

    def save_slot(slot: int) -> None:
        path = save_state_slot(pyboy, slot)
        print(f"Saved state {slot} -> {path}")

    def load_slot(slot: int) -> None:
        try:
            path = load_state_slot(pyboy, slot)
            print(f"Loaded state {slot} <- {path}")
        except FileNotFoundError as exc:
            print(str(exc))

    print("Running. Close the window or press Ctrl+C in the console to stop.")
    print("Controls: WASD move, Z/A, X/B, C/Enter=Start, V/Space=Select | F5/F6 speed -/+ | F1-3 save, F7-9 load | F10 edit memory")
    print("Memory edit: use field keys (e.g., player_x, party[0].level) or hex addr like D20D. Bytes accept hex pairs, numbers accept dec/hex.")
    last_panel = 0.0
    try:
        while pyboy.tick():
            for key, (press_event, release_event) in keymap.items():
                is_down = keyboard.is_pressed(key)
                if is_down and key not in held_keys:
                    pyboy.send_input(press_event)
                    held_keys.add(key)
                elif not is_down and key in held_keys:
                    pyboy.send_input(release_event)
                    held_keys.remove(key)

            # Edge-triggered control keys
            for key, action in control_keys.items():
                is_down = keyboard.is_pressed(key)
                if is_down and key not in held_controls:
                    held_controls.add(key)
                    if action == "speed_up":
                        adjust_speed(1.5)
                    elif action == "speed_down":
                        adjust_speed(1 / 1.5)
                    elif action.startswith("save_"):
                        slot = int(action[-1])
                        save_slot(slot)
                    elif action.startswith("load_"):
                        slot = int(action[-1])
                        load_slot(slot)
                    elif action == "mem_edit":
                        print("Entering memory edit (emulation paused until done)...")
                        prompt_memory_edit(pyboy.memory)
                elif not is_down and key in held_controls:
                    held_controls.remove(key)

            now = time.time()
            if now - last_panel > 2.5:
                print_memory_panel(pyboy.memory)
                last_panel = now

            time.sleep(0.005)  # trim CPU use; adjust if input feels laggy

        print("Emulation ended (window closed or quit).")
    finally:
        try:
            STATE_DIR.mkdir(exist_ok=True)
            with open(PERSIST_STATE, "wb") as f:
                pyboy.save_state(f)
            print(f"Saved persistent state to {PERSIST_STATE}")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to save persistent state: {exc}")
        pyboy.stop(save=False)


if __name__ == "__main__":
    main()
