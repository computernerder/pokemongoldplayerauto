import pytest

import gsc_memory_lib as gml


class FakeMem:
    def __init__(self):
        self.mem = bytearray(0x20000)

    def read_mem(self, addr: int, size: int) -> bytes:
        return bytes(self.mem[addr:addr + size])

    def write_mem(self, addr: int, data: bytes):
        self.mem[addr:addr + len(data)] = data


@pytest.mark.parametrize("val,expected", [
    (0, b"\x00\x00\x00"),
    (1, b"\x00\x00\x01"),
    (12, b"\x00\x00\x12"),
    (123456, b"\x12\x34\x56"),
    (999999, b"\x99\x99\x99"),
])
def test_bcd_roundtrip(val, expected):
    encoded = gml._encode_u24_bcd(val)
    assert encoded == expected
    assert gml._decode_u24_bcd(encoded) == min(val, 999999)


def test_bankaddr_offsets():
    assert gml.bankaddr_to_file_offset(gml.RomBankAddr(0, 0x0000)) == 0x0000
    assert gml.bankaddr_to_file_offset(gml.RomBankAddr(0, 0x3FFF)) == 0x3FFF
    assert gml.bankaddr_to_file_offset(gml.RomBankAddr(1, 0x4000)) == 0x4000
    assert gml.bankaddr_to_file_offset(gml.RomBankAddr(2, 0x4000)) == 0x8000
    with pytest.raises(ValueError):
        gml.bankaddr_to_file_offset(gml.RomBankAddr(0, 0x4000))
    with pytest.raises(ValueError):
        gml.bankaddr_to_file_offset(gml.RomBankAddr(1, 0x3FFF))


def test_read_write_field_core():
    fm = FakeMem()
    money_field = gml.RAM_FIELDS_CORE["money"]
    gml.write_field(fm.write_mem, money_field, 54321)
    assert gml.read_field(fm.read_mem, money_field) == 54321
    bike_field = gml.RAM_FIELDS_CORE["on_bike_flag"]
    gml.write_field(fm.write_mem, bike_field, 1)
    assert gml.read_field(fm.read_mem, bike_field) == 1


def test_party_field_helpers_bounds():
    with pytest.raises(ValueError):
        gml.party_mon_base(-1)
    with pytest.raises(ValueError):
        gml.party_mon_base(6)
    addr0 = gml.party_mon_base(0)
    addr5 = gml.party_mon_base(5)
    assert addr5 - addr0 == 5 * gml.PARTY_MON_STRUCT_SIZE


def test_party_name_helpers_bounds_and_stride():
    with pytest.raises(ValueError):
        gml.party_ot_name_addr(-1)
    with pytest.raises(ValueError):
        gml.party_nickname_addr(6)

    assert gml.party_ot_name_addr(0) == gml.PARTY_OT_NAMES_START
    assert gml.party_nickname_addr(0) == gml.PARTY_NICKNAMES_START
    assert gml.party_ot_name_addr(1) - gml.party_ot_name_addr(0) == gml.PARTY_NAME_LEN
    assert gml.party_nickname_addr(5) - gml.party_nickname_addr(0) == 5 * gml.PARTY_NAME_LEN


def test_rom_field_read_file_range():
    # build dummy rom with incremental bytes
    rom = bytes(range(256)) * 400
    f = gml.ROM_FIELDS["wild.johto_land"]
    blob = gml.read_rom_field(rom, f)
    expected = rom[f.file_range.start_off:f.file_range.end_off_excl]
    assert blob == expected
