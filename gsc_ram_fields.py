#!/usr/bin/env python3
"""
gsc_ram_fields.py - Typed RAM field descriptors for Pokémon Gold/Silver (GSC)

Designed to pair with a raw-memory accessor (PyBoy, BizHawk, mGBA, etc.).
This file does NOT assume any particular emulator API; you provide the
read/write callbacks.

Companion to: gsc_ram_map.py (address constants + party slot helpers)
Source reference: Data Crystal GSC RAM map.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Iterable, Optional


class Encoding(str, Enum):
    U8 = "u8"
    U16_LE = "u16_le"
    U16_BE = "u16_be"
    U24_LE = "u24_le"
    U24_BCD = "u24_bcd"  # Money is commonly 3-byte BCD
    BYTES = "bytes"
    TEXT_GSC = "text_gsc"  # Placeholder: implement decode/encode in your project


@dataclass(frozen=True)
class MemField:
    key: str
    addr: int
    size: int
    enc: Encoding
    doc: str = ""


# ---------------------------------------------------------------------------
# Minimal encode/decode helpers (swap out if you prefer your own)
# ---------------------------------------------------------------------------

def _decode_u16_le(b: bytes) -> int:
    return b[0] | (b[1] << 8)


def _decode_u16_be(b: bytes) -> int:
    return (b[0] << 8) | b[1]


def _decode_u24_le(b: bytes) -> int:
    return b[0] | (b[1] << 8) | (b[2] << 16)


def _decode_u24_bcd(b: bytes) -> int:
    digits = []
    for x in b:
        digits.append((x >> 4) & 0xF)
        digits.append(x & 0xF)
    val = 0
    for d in digits:
        val = (val * 10) + d
    return val


def _encode_u16_le(v: int) -> bytes:
    return bytes((v & 0xFF, (v >> 8) & 0xFF))


def _encode_u16_be(v: int) -> bytes:
    return bytes(((v >> 8) & 0xFF, v & 0xFF))


def _encode_u24_le(v: int) -> bytes:
    return bytes((v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF))


def _encode_u24_bcd(v: int) -> bytes:
    if v < 0:
        v = 0
    if v > 999_999:
        v = 999_999
    s = f"{v:06d}"
    nibbles = [int(ch) for ch in s]
    out = bytearray()
    for i in range(0, 6, 2):
        out.append((nibbles[i] << 4) | nibbles[i + 1])
    return bytes(out)


ReadFn = Callable[[int, int], bytes]  # (addr, size) -> bytes
WriteFn = Callable[[int, bytes], None]  # (addr, data) -> None


def read_field(read_mem: ReadFn, field: MemField):
    raw = read_mem(field.addr, field.size)

    if field.enc == Encoding.U8:
        return raw[0]
    if field.enc == Encoding.U16_LE:
        return _decode_u16_le(raw)
    if field.enc == Encoding.U16_BE:
        return _decode_u16_be(raw)
    if field.enc == Encoding.U24_LE:
        return _decode_u24_le(raw)
    if field.enc == Encoding.U24_BCD:
        return _decode_u24_bcd(raw)
    if field.enc == Encoding.BYTES:
        return raw
    if field.enc == Encoding.TEXT_GSC:
        return raw

    raise ValueError(f"Unhandled encoding: {field.enc}")


def write_field(write_mem: WriteFn, field: MemField, value):
    if field.enc == Encoding.U8:
        write_mem(field.addr, bytes((int(value) & 0xFF,)))
        return
    if field.enc == Encoding.U16_LE:
        write_mem(field.addr, _encode_u16_le(int(value)))
        return
    if field.enc == Encoding.U16_BE:
        write_mem(field.addr, _encode_u16_be(int(value)))
        return
    if field.enc == Encoding.U24_LE:
        write_mem(field.addr, _encode_u24_le(int(value)))
        return
    if field.enc == Encoding.U24_BCD:
        write_mem(field.addr, _encode_u24_bcd(int(value)))
        return
    if field.enc == Encoding.BYTES:
        b = bytes(value)
        if len(b) != field.size:
            raise ValueError(f"{field.key}: expected {field.size} bytes, got {len(b)}")
        write_mem(field.addr, b)
        return
    if field.enc == Encoding.TEXT_GSC:
        b = bytes(value)
        if len(b) != field.size:
            raise ValueError(f"{field.key}: expected {field.size} bytes, got {len(b)}")
        write_mem(field.addr, b)
        return

    raise ValueError(f"Unhandled encoding: {field.enc}")


FIELDS: Dict[str, MemField] = {
    "player_sprite_id": MemField("player_sprite_id", 0xD1FF, 1, Encoding.U8, "Player sprite ID"),
    "player_clothes": MemField("player_clothes", 0xD203, 1, Encoding.U8, "Player clothes"),
    "options": MemField("options", 0xD199, 1, Encoding.U8, "Options byte"),
    "wild_battles_enabled": MemField("wild_battles_enabled", 0xD20B, 1, Encoding.U8, "Wild battles flag"),
    "player_x": MemField("player_x", 0xD20D, 1, Encoding.U8, "Player X"),
    "player_y": MemField("player_y", 0xD20E, 1, Encoding.U8, "Player Y"),
    "map_bank": MemField("map_bank", 0xDA00, 1, Encoding.U8, "Map bank"),
    "map_number": MemField("map_number", 0xDA01, 1, Encoding.U8, "Map number"),
    "overworld_xy": MemField("overworld_xy", 0xDA02, 2, Encoding.BYTES, "Overworld X then Y"),
    "money": MemField("money", 0xD573, 3, Encoding.U24_BCD, "Money (3-byte BCD)"),
    "mom_money": MemField("mom_money", 0xD576, 3, Encoding.U24_BCD, "Money held by Mom"),
    "casino_coins": MemField("casino_coins", 0xD57A, 2, Encoding.U16_LE, "Casino coins"),
    "johto_badges": MemField("johto_badges", 0xD57C, 1, Encoding.U8, "Johto badge bits"),
    "kanto_badges": MemField("kanto_badges", 0xD57D, 1, Encoding.U8, "Kanto badge bits"),
    "party_count": MemField("party_count", 0xDA22, 1, Encoding.U8, "Party count"),
    "party_species": MemField("party_species", 0xDA23, 6, Encoding.BYTES, "Party species list"),
    "bag_item_count": MemField("bag_item_count", 0xD5B7, 1, Encoding.U8, "Bag item count"),
    "key_item_count": MemField("key_item_count", 0xD5E1, 1, Encoding.U8, "Key item count"),
    "ball_count": MemField("ball_count", 0xD5FC, 1, Encoding.U8, "Ball count"),
    "pc_item_count": MemField("pc_item_count", 0xD616, 1, Encoding.U8, "PC item count"),
    "repel_steps": MemField("repel_steps", 0xD9EB, 1, Encoding.U8, "Repel steps left"),
    "on_bike_flag": MemField("on_bike_flag", 0xD682, 1, Encoding.U8, "On bike flag"),
    "battle_type": MemField("battle_type", 0xD116, 1, Encoding.U8, "Battle type"),
    "wild_species": MemField("wild_species", 0xD0ED, 1, Encoding.U8, "Wild species"),
    "wild_level": MemField("wild_level", 0xD0FC, 1, Encoding.U8, "Wild/enemy level"),
    "your_hp_battle": MemField("your_hp_battle", 0xCB1C, 2, Encoding.U16_BE, "Your HP in battle"),
    "enemy_level": MemField("enemy_level", 0xD0FC, 1, Encoding.U8, "Enemy level"),
    "enemy_status": MemField("enemy_status", 0xD0FD, 1, Encoding.U8, "Enemy status"),
}


PARTY_MON_1_BASE = 0xDA2A
PARTY_MON_STRUCT_SIZE = 0x30

_OFF_SPECIES = 0x00
_OFF_ITEM = 0x01
_OFF_MOVES = 0x02
_OFF_ID = 0x06
_OFF_EXP = 0x08
_OFF_PP = 0x17
_OFF_HAPPINESS = 0x1B
_OFF_POKERUS = 0x1C
_OFF_LEVEL = 0x1F
_OFF_STATUS = 0x20
_OFF_HP = 0x22
_OFF_MAX_HP = 0x24
_OFF_ATK = 0x26
_OFF_DEF = 0x28
_OFF_SPD = 0x2A
_OFF_SPDEF = 0x2C
_OFF_SPATK = 0x2E


def party_mon_base(slot_index_0_to_5: int) -> int:
    if not (0 <= slot_index_0_to_5 <= 5):
        raise ValueError("slot_index must be in range 0..5")
    return PARTY_MON_1_BASE + (slot_index_0_to_5 * PARTY_MON_STRUCT_SIZE)


def party_fields_for_slot(slot_index_0_to_5: int) -> Dict[str, MemField]:
    b = party_mon_base(slot_index_0_to_5)
    pfx = f"party[{slot_index_0_to_5}]"

    return {
        f"{pfx}.species": MemField(f"{pfx}.species", b + _OFF_SPECIES, 1, Encoding.U8, "Species"),
        f"{pfx}.item": MemField(f"{pfx}.item", b + _OFF_ITEM, 1, Encoding.U8, "Held item"),
        f"{pfx}.moves": MemField(f"{pfx}.moves", b + _OFF_MOVES, 4, Encoding.BYTES, "Moves"),
        f"{pfx}.id": MemField(f"{pfx}.id", b + _OFF_ID, 2, Encoding.U16_BE, "OT/mon ID"),
        f"{pfx}.exp": MemField(f"{pfx}.exp", b + _OFF_EXP, 3, Encoding.U24_LE, "EXP"),
        f"{pfx}.pp": MemField(f"{pfx}.pp", b + _OFF_PP, 4, Encoding.BYTES, "PP"),
        f"{pfx}.happiness": MemField(f"{pfx}.happiness", b + _OFF_HAPPINESS, 1, Encoding.U8, "Happiness"),
        f"{pfx}.pokerus": MemField(f"{pfx}.pokerus", b + _OFF_POKERUS, 1, Encoding.U8, "Pokerus"),
        f"{pfx}.level": MemField(f"{pfx}.level", b + _OFF_LEVEL, 1, Encoding.U8, "Level"),
        f"{pfx}.status": MemField(f"{pfx}.status", b + _OFF_STATUS, 2, Encoding.U16_BE, "Status"),
        f"{pfx}.hp": MemField(f"{pfx}.hp", b + _OFF_HP, 2, Encoding.U16_BE, "HP"),
        f"{pfx}.max_hp": MemField(f"{pfx}.max_hp", b + _OFF_MAX_HP, 2, Encoding.U16_BE, "Max HP"),
        f"{pfx}.atk": MemField(f"{pfx}.atk", b + _OFF_ATK, 2, Encoding.U16_BE, "Attack"),
        f"{pfx}.def": MemField(f"{pfx}.def", b + _OFF_DEF, 2, Encoding.U16_BE, "Defense"),
        f"{pfx}.spd": MemField(f"{pfx}.spd", b + _OFF_SPD, 2, Encoding.U16_BE, "Speed"),
        f"{pfx}.spdef": MemField(f"{pfx}.spdef", b + _OFF_SPDEF, 2, Encoding.U16_BE, "Sp Def"),
        f"{pfx}.spatk": MemField(f"{pfx}.spatk", b + _OFF_SPATK, 2, Encoding.U16_BE, "Sp Atk"),
    }


def iter_all_party_fields():
    for i in range(6):
        yield from party_fields_for_slot(i).values()


def build_catalog(include_party: bool = True) -> Dict[str, MemField]:
    cat = dict(FIELDS)
    if include_party:
        for f in iter_all_party_fields():
            cat[f.key] = f
    return cat


def snapshot(read_mem: ReadFn, keys: Optional[Iterable[str]] = None) -> Dict[str, object]:
    cat = build_catalog(include_party=True)
    if keys is None:
        keys = cat.keys()

    out: Dict[str, object] = {}
    for k in keys:
        field = cat[k]
        out[k] = read_field(read_mem, field)
    return out
