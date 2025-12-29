"""
gsc_ram_map.py - Pokémon Gold/Silver RAM map constants (Game Boy Color)

Addresses based on:
- https://datacrystal.tcrf.net/wiki/Pok%C3%A9mon_Gold_and_Silver/RAM_map

Notes:
- All addresses are CPU address space (as exposed by most emulators' "system memory" views).
- Multi-byte fields: endianness/encoding varies by field (money is typically 3-byte BCD in GSC).
"""

# ---------------------------------------------------------------------------
# Miscellaneous
# ---------------------------------------------------------------------------

LOW_HP_WARNING = 0xC1A6
BRIGHTNESS = 0xC1CF

MAP_BUFFER_START = 0xC700
MAP_BUFFER_END = 0xCAFF

RUINS_OF_ALPH_PUZZLE_START = 0xC5D0
RUINS_OF_ALPH_PUZZLE_END = 0xC5F3

# ---------------------------------------------------------------------------
# In-battle: Your Pokémon
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# In-battle: Opposing Pokémon
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Shop
# ---------------------------------------------------------------------------

MART_SLOTS_START = 0xCFED
MART_SLOTS_END = 0xCFF1
MART_NUM_ITEMS = 0xD140

# ---------------------------------------------------------------------------
# Overworld / Miscellany
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Game Settings / Trainer Identity / Clock
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# PC Storage: Box names
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Party Pokémon
# ---------------------------------------------------------------------------

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


def party_mon_base(slot_index_0_to_5: int) -> int:
    if not (0 <= slot_index_0_to_5 <= 5):
        raise ValueError("slot_index must be in range 0..5")
    return PARTY_MON_1_BASE + (slot_index_0_to_5 * PARTY_MON_STRUCT_SIZE)


def party_mon_field_addr(slot_index_0_to_5: int, field_offset: int) -> int:
    return party_mon_base(slot_index_0_to_5) + field_offset
