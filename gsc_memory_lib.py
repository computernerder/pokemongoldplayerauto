#!/usr/bin/env python3
"""
gsc_memory_lib.py - Single-file GSC (Pokémon Gold/Silver) memory library

This consolidates RAM constants, typed RAM field helpers, ROM bank/range helpers, and typed ROM fields.
It stays emulator-agnostic: provide read_mem(addr, size)->bytes and write_mem(addr, bytes)->None.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Iterable, Optional

# ============================================================================
# 1) RAM MAP CONSTANTS
# ============================================================================

LOW_HP_WARNING = 0xC1A6
BRIGHTNESS = 0xC1CF

MAP_BUFFER_START = 0xC700
MAP_BUFFER_END = 0xCAFF

RUINS_OF_ALPH_PUZZLE_START = 0xC5D0
RUINS_OF_ALPH_PUZZLE_END = 0xC5F3

BATTLE_YOUR_HELD_ITEM = 0xCB0D
BATTLE_YOUR_MOVES_START = 0xCB0E
BATTLE_YOUR_MOVES_END = 0xCB11
BATTLE_YOUR_PP_START = 0xCB14
BATTLE_YOUR_PP_END = 0xCB17
BATTLE_YOUR_STATUS = 0xCB1A
BATTLE_YOUR_HP_IN_BATTLE = 0xCB1C
BATTLE_YOUR_TYPES = 0xCB2A
BATTLE_YOUR_SUBSTITUTE = 0xCB49
BATTLE_MONEY_EARNED = 0xCB65
BATTLE_EXP_GIVEN = 0xCF7E
BATTLE_YOUR_CURRENT_ATTACK = 0xCBC1

BATTLE_CAUGHT_MOVES_START = 0xCC13
BATTLE_CAUGHT_MOVES_END = 0xCC16
BATTLE_ENEMY_ITEM = 0xD0F0
BATTLE_ENEMY_MOVES_START = 0xD0F1
BATTLE_ENEMY_MOVES_END = 0xD0F4
BATTLE_ENEMY_DVS_AD = 0xD0F5
BATTLE_ENEMY_DVS_SS = 0xD0F5
BATTLE_ENEMY_LEVEL = 0xD0FC
BATTLE_ENEMY_STATUS = 0xD0FD
BATTLE_ENEMY_STATS_START = 0xD0FF
BATTLE_ENEMY_STATS_END = 0xD10C
BATTLE_TYPE = 0xD116
BATTLE_ENEMY_SEX = 0xD119
BATTLE_ENEMY_TYPES = 0xD127
BATTLE_ENEMY_PENDING_DAMAGE = 0xD141
BATTLE_ENEMY_MAGNITUDE = 0xD151
BATTLE_ENEMY_MOVES_ALT_START = 0xD149
BATTLE_ENEMY_MOVES_ALT_END = 0xD14C
BATTLE_OPPONENT_PARTY_COUNT = (0xDD55, 0xDD5B)

WILD_POKEMON_SPECIES = 0xD0ED
WILD_POKEMON_LEVEL = 0xD0FC

MART_SLOTS_START = 0xCFED
MART_SLOTS_END = 0xCFF1
MART_NUM_ITEMS = 0xD140

PLAYER_SPRITE_ID = 0xD1FF
PLAYER_CLOTHES = 0xD203
PLAYER_X_POS = 0xD20D
PLAYER_Y_POS = 0xD20E
MAP_BANK = 0xDA00
MAP_NUMBER = 0xDA01
OVERWORLD_XY = 0xDA02
ON_BIKE_FLAG = 0xD682
REPEL_STEPS_LEFT = 0xD9EB
PARK_TIME = 0xD193
OPTIONS_BYTE = 0xD199
BUG_CONTEST_CAUGHT_SPECIES = 0xDCE7
BUG_CONTEST_CAUGHT_LEVEL = 0xDD06
BUG_CONTEST_CAUGHT_STATS = (0xDD09, 0xDD16)
TRAINER_ID = (0xD1A1, 0xD1A2)
TRAINER_NAME = (0xD1A3, 0xD1AC)
RIVAL_NAME = (0xD1BC, 0xD1B5)
CLOCK_DAY = (0xD1DC, 0xD1E0)
CLOCK_TIME = (0xD1EB, 0xD1EF)
WILD_BATTLES_ENABLED = 0xD20B
MONEY = (0xD573, 0xD575)
MOM_MONEY = (0xD576, 0xD578)
CASINO_COINS = (0xD57A, 0xD57B)
JOHTO_BADGES = 0xD57C
KANTO_BADGES = 0xD57D
JOHTO_BADGE_FALKNER = 0x01
JOHTO_BADGE_BUGSY = 0x02
JOHTO_BADGE_WHITNEY = 0x04
JOHTO_BADGE_MORTY = 0x08
JOHTO_BADGE_JASMINE = 0x10
JOHTO_BADGE_CHUCK = 0x20
JOHTO_BADGE_PRYCE = 0x40
JOHTO_BADGE_CLAIR = 0x80
TMS_START = 0xD57E
TMS_END = 0xD5AF
HMS_START = 0xD5B0
HMS_END = 0xD5B6
BAG_ITEM_COUNT = 0xD5B7
BAG_ITEMS_START = 0xD5B8
BAG_ITEMS_END_OF_LIST = 0xD5E0
KEY_ITEM_COUNT = 0xD5E1
KEY_ITEMS_START = 0xD5E2
KEY_ITEMS_END = 0xD5FA
KEY_ITEMS_END_OF_LIST = 0xD5FB
BALL_COUNT = 0xD5FC
BALLS_START = 0xD5FD
BALLS_END_OF_LIST = 0xD615
PC_STORED_ITEMS_COUNT = 0xD616
PC_STORED_ITEMS_START = 0xD617
BOX_NAME_1 = (0xD8BF, 0xD8C7)
BOX_NAME_2 = (0xD8C8, 0xD8D0)
BOX_NAME_3 = (0xD8D1, 0xD8D9)
BOX_NAME_4 = (0xD8DA, 0xD8E2)
BOX_NAME_5 = (0xD8E3, 0xD8EB)
BOX_NAME_6 = (0xD8EC, 0xD8F4)
BOX_NAME_7 = (0xD8F5, 0xD8FD)
BOX_NAME_8 = (0xD8FE, 0xD906)
BOX_NAME_9 = (0xD907, 0xD90F)
BOX_NAME_10 = (0xD910, 0xD918)
BOX_NAME_11 = (0xD919, 0xD921)
BOX_NAME_12 = (0xD922, 0xD92A)
BOX_NAME_13 = (0xD92B, 0xD933)
BOX_NAME_14 = (0xD934, 0xD93C)
BOX_NAMES = (
    BOX_NAME_1,
    BOX_NAME_2,
    BOX_NAME_3,
    BOX_NAME_4,
    BOX_NAME_5,
    BOX_NAME_6,
    BOX_NAME_7,
    BOX_NAME_8,
    BOX_NAME_9,
    BOX_NAME_10,
    BOX_NAME_11,
    BOX_NAME_12,
    BOX_NAME_13,
    BOX_NAME_14,
)
PARTY_COUNT = 0xDA22
PARTY_SPECIES_LIST_START = 0xDA23
PARTY_SPECIES_LIST_END = 0xDA28
PARTY_SPECIES_LIST_TERMINATOR = 0xDA29
PARTY_MON_STRUCT_SIZE = 0x30
PARTY_MON_1_BASE = 0xDA2A
PARTY_MON_SPECIES_OFF = 0x00
PARTY_MON_HELD_ITEM_OFF = 0x01
PARTY_MON_MOVES_OFF = 0x02
PARTY_MON_ID_OFF = 0x06
PARTY_MON_EXP_OFF = 0x08
PARTY_MON_HP_EV_OFF = 0x0B
PARTY_MON_ATK_EV_OFF = 0x0D
PARTY_MON_DEF_EV_OFF = 0x0F
PARTY_MON_SPD_EV_OFF = 0x11
PARTY_MON_SPC_EV_OFF = 0x13
PARTY_MON_IV_AD_OFF = 0x15
PARTY_MON_IV_SS_OFF = 0x16
PARTY_MON_PP_OFF = 0x17
PARTY_MON_HAPPINESS_OFF = 0x1B
PARTY_MON_POKERUS_OFF = 0x1C
PARTY_MON_CAUGHT_DATA_OFF = 0x1D
PARTY_MON_LEVEL_OFF = 0x1F
PARTY_MON_STATUS_OFF = 0x20
PARTY_MON_HP_OFF = 0x22
PARTY_MON_MAX_HP_OFF = 0x24
PARTY_MON_ATK_OFF = 0x26
PARTY_MON_DEF_OFF = 0x28
PARTY_MON_SPD_OFF = 0x2A
PARTY_MON_SPDEF_OFF = 0x2C
PARTY_MON_SPATK_OFF = 0x2E

# Party names (OT names + nicknames)
# Data Crystal RAM map: https://datacrystal.tcrf.net/wiki/Pok%C3%A9mon_Gold_and_Silver/RAM_map#Pokemon_Names
PARTY_NAME_LEN = 0x0B  # 11 bytes per entry (10 chars + 0x50 terminator/padding)
PARTY_OT_NAMES_START = 0xDB4A
PARTY_NICKNAMES_START = 0xDB8C


def party_ot_name_addr(slot_index_0_to_5: int) -> int:
    if not (0 <= slot_index_0_to_5 <= 5):
        raise ValueError("slot_index must be in range 0..5")
    return PARTY_OT_NAMES_START + (slot_index_0_to_5 * PARTY_NAME_LEN)


def party_nickname_addr(slot_index_0_to_5: int) -> int:
    if not (0 <= slot_index_0_to_5 <= 5):
        raise ValueError("slot_index must be in range 0..5")
    return PARTY_NICKNAMES_START + (slot_index_0_to_5 * PARTY_NAME_LEN)


def party_mon_base(slot_index_0_to_5: int) -> int:
    if not (0 <= slot_index_0_to_5 <= 5):
        raise ValueError("slot_index must be in range 0..5")
    return PARTY_MON_1_BASE + (slot_index_0_to_5 * PARTY_MON_STRUCT_SIZE)


def party_mon_field_addr(slot_index_0_to_5: int, field_offset: int) -> int:
    return party_mon_base(slot_index_0_to_5) + field_offset


# ============================================================================
# 2) TYPED RAM FIELDS
# ============================================================================

class Encoding(str, Enum):
    U8 = "u8"
    U16_LE = "u16_le"
    U16_BE = "u16_be"
    U24_LE = "u24_le"
    U24_BCD = "u24_bcd"
    BYTES = "bytes"
    TEXT_GSC = "text_gsc"


@dataclass(frozen=True)
class MemField:
    key: str
    addr: int
    size: int
    enc: Encoding
    doc: str = ""


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
    if v > 999999:
        v = 999999
    s = f"{v:06d}"
    nibbles = [int(ch) for ch in s]
    out = bytearray()
    for i in range(0, 6, 2):
        out.append((nibbles[i] << 4) | nibbles[i + 1])
    return bytes(out)


ReadFn = Callable[[int, int], bytes]
WriteFn = Callable[[int, bytes], None]


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


RAM_FIELDS_CORE: Dict[str, MemField] = {
    "player_sprite_id": MemField("player_sprite_id", PLAYER_SPRITE_ID, 1, Encoding.U8, "Player sprite ID"),
    "player_clothes": MemField("player_clothes", PLAYER_CLOTHES, 1, Encoding.U8, "Player clothes"),
    "options": MemField("options", OPTIONS_BYTE, 1, Encoding.U8, "Options byte"),
    "trainer_id": MemField("trainer_id", TRAINER_ID[0], 2, Encoding.U16_LE, "Trainer ID"),
    "player_name": MemField("player_name", TRAINER_NAME[0], TRAINER_NAME[1] - TRAINER_NAME[0] + 1, Encoding.TEXT_GSC, "Player name (GSC text)"),
    "wild_battles_enabled": MemField("wild_battles_enabled", WILD_BATTLES_ENABLED, 1, Encoding.U8, "Wild battles flag"),
    "player_x": MemField("player_x", PLAYER_X_POS, 1, Encoding.U8, "Player X"),
    "player_y": MemField("player_y", PLAYER_Y_POS, 1, Encoding.U8, "Player Y"),
    "map_bank": MemField("map_bank", MAP_BANK, 1, Encoding.U8, "Map bank"),
    "map_number": MemField("map_number", MAP_NUMBER, 1, Encoding.U8, "Map number"),
    "overworld_xy": MemField("overworld_xy", OVERWORLD_XY, 2, Encoding.BYTES, "Overworld X then Y"),
    "money": MemField("money", MONEY[0], 3, Encoding.U24_BCD, "Money (3-byte BCD)"),
    "mom_money": MemField("mom_money", MOM_MONEY[0], 3, Encoding.U24_BCD, "Money held by Mom"),
    "casino_coins": MemField("casino_coins", CASINO_COINS[0], 2, Encoding.U16_LE, "Casino coins"),
    "johto_badges": MemField("johto_badges", JOHTO_BADGES, 1, Encoding.U8, "Johto badges bitfield"),
    "kanto_badges": MemField("kanto_badges", KANTO_BADGES, 1, Encoding.U8, "Kanto badges bitfield"),
    "party_count": MemField("party_count", PARTY_COUNT, 1, Encoding.U8, "Party count"),
    "party_species": MemField("party_species", PARTY_SPECIES_LIST_START, 6, Encoding.BYTES, "Party species list"),
    "bag_item_count": MemField("bag_item_count", BAG_ITEM_COUNT, 1, Encoding.U8, "Bag item count"),
    "key_item_count": MemField("key_item_count", KEY_ITEM_COUNT, 1, Encoding.U8, "Key item count"),
    "ball_count": MemField("ball_count", BALL_COUNT, 1, Encoding.U8, "Ball count"),
    "pc_item_count": MemField("pc_item_count", PC_STORED_ITEMS_COUNT, 1, Encoding.U8, "PC item count"),
    "repel_steps": MemField("repel_steps", REPEL_STEPS_LEFT, 1, Encoding.U8, "Repel steps left"),
    "on_bike_flag": MemField("on_bike_flag", ON_BIKE_FLAG, 1, Encoding.U8, "On bike flag"),
    "battle_type": MemField("battle_type", BATTLE_TYPE, 1, Encoding.U8, "Battle type"),
    "wild_species": MemField("wild_species", WILD_POKEMON_SPECIES, 1, Encoding.U8, "Wild species"),
    "wild_level": MemField("wild_level", WILD_POKEMON_LEVEL, 1, Encoding.U8, "Wild/enemy level"),
    "your_hp_battle": MemField("your_hp_battle", BATTLE_YOUR_HP_IN_BATTLE, 2, Encoding.U16_BE, "Your HP in battle"),
    "enemy_status": MemField("enemy_status", BATTLE_ENEMY_STATUS, 1, Encoding.U8, "Enemy status"),
}


def party_fields_for_slot(slot_index_0_to_5: int) -> Dict[str, MemField]:
    base = party_mon_base(slot_index_0_to_5)
    pfx = f"party[{slot_index_0_to_5}]"
    return {
        f"{pfx}.species": MemField(f"{pfx}.species", base + PARTY_MON_SPECIES_OFF, 1, Encoding.U8, "Species"),
        f"{pfx}.item": MemField(f"{pfx}.item", base + PARTY_MON_HELD_ITEM_OFF, 1, Encoding.U8, "Held item"),
        f"{pfx}.moves": MemField(f"{pfx}.moves", base + PARTY_MON_MOVES_OFF, 4, Encoding.BYTES, "Moves"),
        f"{pfx}.id": MemField(f"{pfx}.id", base + PARTY_MON_ID_OFF, 2, Encoding.U16_BE, "OT/mon ID"),
        f"{pfx}.exp": MemField(f"{pfx}.exp", base + PARTY_MON_EXP_OFF, 3, Encoding.U24_LE, "EXP"),
        f"{pfx}.pp": MemField(f"{pfx}.pp", base + PARTY_MON_PP_OFF, 4, Encoding.BYTES, "PP"),
        f"{pfx}.happiness": MemField(f"{pfx}.happiness", base + PARTY_MON_HAPPINESS_OFF, 1, Encoding.U8, "Happiness"),
        f"{pfx}.pokerus": MemField(f"{pfx}.pokerus", base + PARTY_MON_POKERUS_OFF, 1, Encoding.U8, "Pokerus"),
        f"{pfx}.level": MemField(f"{pfx}.level", base + PARTY_MON_LEVEL_OFF, 1, Encoding.U8, "Level"),
        f"{pfx}.status": MemField(f"{pfx}.status", base + PARTY_MON_STATUS_OFF, 2, Encoding.U16_BE, "Status"),
        f"{pfx}.hp": MemField(f"{pfx}.hp", base + PARTY_MON_HP_OFF, 2, Encoding.U16_BE, "HP"),
        f"{pfx}.max_hp": MemField(f"{pfx}.max_hp", base + PARTY_MON_MAX_HP_OFF, 2, Encoding.U16_BE, "Max HP"),
        f"{pfx}.atk": MemField(f"{pfx}.atk", base + PARTY_MON_ATK_OFF, 2, Encoding.U16_BE, "Attack"),
        f"{pfx}.def": MemField(f"{pfx}.def", base + PARTY_MON_DEF_OFF, 2, Encoding.U16_BE, "Defense"),
        f"{pfx}.spd": MemField(f"{pfx}.spd", base + PARTY_MON_SPD_OFF, 2, Encoding.U16_BE, "Speed"),
        f"{pfx}.spdef": MemField(f"{pfx}.spdef", base + PARTY_MON_SPDEF_OFF, 2, Encoding.U16_BE, "Sp Def"),
        f"{pfx}.spatk": MemField(f"{pfx}.spatk", base + PARTY_MON_SPATK_OFF, 2, Encoding.U16_BE, "Sp Atk"),
    }


def iter_all_party_fields() -> Iterable[MemField]:
    for i in range(6):
        yield from party_fields_for_slot(i).values()


def build_ram_catalog(include_party: bool = True) -> Dict[str, MemField]:
    cat = dict(RAM_FIELDS_CORE)
    if include_party:
        for f in iter_all_party_fields():
            cat[f.key] = f
    return cat


def snapshot_ram(read_mem: ReadFn, keys: Optional[Iterable[str]] = None) -> Dict[str, object]:
    cat = build_ram_catalog(include_party=True)
    if keys is None:
        keys = cat.keys()
    return {k: read_field(read_mem, cat[k]) for k in keys}


# ============================================================================
# 3) ROM MAP HELPERS
# ============================================================================

@dataclass(frozen=True)
class RomBankAddr:
    bank: int
    addr: int


def bankaddr_to_file_offset(p: RomBankAddr) -> int:
    if p.bank < 0:
        raise ValueError("bank must be >= 0")
    if p.bank == 0:
        if not (0x0000 <= p.addr <= 0x3FFF):
            raise ValueError("bank 0 addr must be 0x0000..0x3FFF")
        return p.addr
    if not (0x4000 <= p.addr <= 0x7FFF):
        raise ValueError("bank>0 addr must be 0x4000..0x7FFF")
    return (p.bank * 0x4000) + (p.addr - 0x4000)


@dataclass(frozen=True)
class RomRange:
    start_off: int
    end_off_excl: int
    desc: str = ""


def parse_hex_range(text: str, desc: str = "") -> RomRange:
    a, b = text.split("-", 1)
    start = int(a.strip(), 16)
    end_inclusive = int(b.strip(), 16)
    return RomRange(start, end_inclusive + 1, desc=desc)


PTR_ALL_TILESET_POINTERS = RomBankAddr(0, 0x2DFD)
PTR_ALL_TILESET_POINTERS_PART2 = RomBankAddr(0, 0x2E0F)
PTR_COLORS_SECOND_PART = RomBankAddr(0, 0x2E50)
PTR_POKEMON_STATS = RomBankAddr(0, 0x3A8E)

WILD_PTR_JOHTO_LAND = parse_hex_range("2AA74-2AA75", "Pointer to Johto Pokemon (Land)")
WILD_JOHTO_LAND = parse_hex_range("2AB35-2B667", "Johto Wild Pokemon (Land)")
WILD_JOHTO_WATER = parse_hex_range("2B669-2B7BE", "Johto Wild Pokemon (Water)")
WILD_KANTO_LAND = parse_hex_range("2B7C0-2BD41", "Kanto Wild Pokemon (Land)")
WILD_KANTO_WATER = parse_hex_range("2BD43-2BE1A", "Kanto Wild Pokemon (Water)")
TRAINER_BATTLE_PTRS = parse_hex_range("3993E-399C0", "Pointers to Trainer Battles")
TRAINER_POKEMON_DATA = parse_hex_range("399C1-3B684", "Trainers Pokemon Data")
POKEDEX_ABC_ORDER = parse_hex_range("40C65-40D5F", "ABC Pokedex Order")
POKEDEX_NEW_ORDER = parse_hex_range("40D60-40E5B", "New Pokedex Order")
POKEDEX_TYPES_TEXT = parse_hex_range("40FFE-41085", "Types (POKEDEX)")
MOVES_DATA = parse_hex_range("41AFE-421DB", "Moves Data")
PTR_TABLE_POKEMON_MOVES_EVOL = parse_hex_range("427BD-429B2", "Pointers to Pokemon Moves/Evolution Data")
POKEMON_MOVES_EVOL_DATA = parse_hex_range("429B3-43E56", "Pokemon Moves/Evolution Data")
POKEPIC_POINTERS = parse_hex_range("48000-485DF", "Pointers to Pokepics")
POKEPIC_GRAPHICS = parse_hex_range("485E0-4BFFF", "Pokemon Graphics")
MAP_BANK_POINTERS = parse_hex_range("940ED-94120", "Map Bank Pointers")
MAP_PRIMARY_HEADERS = parse_hex_range("94121-94E11", "Map Primary Headers")
MAP_SECONDARY_HEADERS = parse_hex_range("94E12-965F8", "Map Secondary Headers")


def read_rom_range(rom: bytes, r: RomRange) -> bytes:
    return rom[r.start_off:r.end_off_excl]


def read_rom_bankaddr(rom: bytes, p: RomBankAddr, size: int) -> bytes:
    off = bankaddr_to_file_offset(p)
    return rom[off:off + size]


class RomLocKind(str, Enum):
    FILE_RANGE = "file_range"
    BANK_ADDR = "bank_addr"


@dataclass(frozen=True)
class RomField:
    key: str
    kind: RomLocKind
    desc: str
    file_range: Optional[RomRange] = None
    bank_addr: Optional[RomBankAddr] = None
    size: Optional[int] = None


def read_rom_field(rom: bytes, f: RomField) -> bytes:
    if f.kind == RomLocKind.FILE_RANGE:
        if f.file_range is None:
            raise ValueError(f"{f.key}: missing file_range")
        return read_rom_range(rom, f.file_range)
    if f.kind == RomLocKind.BANK_ADDR:
        if f.bank_addr is None or f.size is None:
            raise ValueError(f"{f.key}: missing bank_addr/size")
        return read_rom_bankaddr(rom, f.bank_addr, f.size)
    raise ValueError(f"Unhandled kind: {f.kind}")


ROM_FIELDS: Dict[str, RomField] = {
    "ptr.all_tileset_pointers": RomField("ptr.all_tileset_pointers", RomLocKind.BANK_ADDR, "Pointer to all tileset pointers (Bank 0)", bank_addr=PTR_ALL_TILESET_POINTERS, size=2),
    "ptr.all_tileset_pointers_part2": RomField("ptr.all_tileset_pointers_part2", RomLocKind.BANK_ADDR, "Pointer to all tileset pointers part 2 (Bank 0)", bank_addr=PTR_ALL_TILESET_POINTERS_PART2, size=2),
    "ptr.colors_second_part": RomField("ptr.colors_second_part", RomLocKind.BANK_ADDR, "Pointer to Colors (Second part) (Bank 0)", bank_addr=PTR_COLORS_SECOND_PART, size=2),
    "ptr.pokemon_stats": RomField("ptr.pokemon_stats", RomLocKind.BANK_ADDR, "Pointer to Pokémon stats (Bank 0)", bank_addr=PTR_POKEMON_STATS, size=2),
    "wild.ptr_johto_land": RomField("wild.ptr_johto_land", RomLocKind.FILE_RANGE, "Pointer to Johto Pokemon (Land)", file_range=WILD_PTR_JOHTO_LAND),
    "wild.johto_land": RomField("wild.johto_land", RomLocKind.FILE_RANGE, "Johto Wild Pokemon (Land)", file_range=WILD_JOHTO_LAND),
    "wild.johto_water": RomField("wild.johto_water", RomLocKind.FILE_RANGE, "Johto Wild Pokemon (Water)", file_range=WILD_JOHTO_WATER),
    "wild.kanto_land": RomField("wild.kanto_land", RomLocKind.FILE_RANGE, "Kanto Wild Pokemon (Land)", file_range=WILD_KANTO_LAND),
    "wild.kanto_water": RomField("wild.kanto_water", RomLocKind.FILE_RANGE, "Kanto Wild Pokemon (Water)", file_range=WILD_KANTO_WATER),
    "trainers.battle_ptrs": RomField("trainers.battle_ptrs", RomLocKind.FILE_RANGE, "Pointers to Trainer Battles", file_range=TRAINER_BATTLE_PTRS),
    "trainers.pokemon_data": RomField("trainers.pokemon_data", RomLocKind.FILE_RANGE, "Trainers Pokemon Data", file_range=TRAINER_POKEMON_DATA),
    "pokedex.abc_order": RomField("pokedex.abc_order", RomLocKind.FILE_RANGE, "ABC Pokedex Order", file_range=POKEDEX_ABC_ORDER),
    "pokedex.new_order": RomField("pokedex.new_order", RomLocKind.FILE_RANGE, "New Pokedex Order", file_range=POKEDEX_NEW_ORDER),
    "pokedex.types_text": RomField("pokedex.types_text", RomLocKind.FILE_RANGE, "Types (POKEDEX)", file_range=POKEDEX_TYPES_TEXT),
    "moves.move_data": RomField("moves.move_data", RomLocKind.FILE_RANGE, "Moves Data", file_range=MOVES_DATA),
    "moves.ptr_table_pokemon_moves_evol": RomField("moves.ptr_table_pokemon_moves_evol", RomLocKind.FILE_RANGE, "Pointers to Pokemon Moves/Evolution Data", file_range=PTR_TABLE_POKEMON_MOVES_EVOL),
    "moves.pokemon_moves_evol_data": RomField("moves.pokemon_moves_evol_data", RomLocKind.FILE_RANGE, "Pokemon Moves/Evolution Data", file_range=POKEMON_MOVES_EVOL_DATA),
    "pokepics.pointers": RomField("pokepics.pointers", RomLocKind.FILE_RANGE, "Pointers to Pokepics", file_range=POKEPIC_POINTERS),
    "pokepics.graphics": RomField("pokepics.graphics", RomLocKind.FILE_RANGE, "Pokemon Graphics blob", file_range=POKEPIC_GRAPHICS),
    "maps.bank_pointers": RomField("maps.bank_pointers", RomLocKind.FILE_RANGE, "Map Bank Pointers", file_range=MAP_BANK_POINTERS),
    "maps.primary_headers": RomField("maps.primary_headers", RomLocKind.FILE_RANGE, "Map Primary Headers", file_range=MAP_PRIMARY_HEADERS),
    "maps.secondary_headers": RomField("maps.secondary_headers", RomLocKind.FILE_RANGE, "Map Secondary Headers", file_range=MAP_SECONDARY_HEADERS),
}


def build_rom_catalog() -> Dict[str, RomField]:
    return dict(ROM_FIELDS)
