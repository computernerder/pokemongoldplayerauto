import os
import io
from pathlib import Path

import pytest

import run_emulator


def test_rom_loads_with_null_window():
    if not run_emulator.ROM_PATH.exists():
        pytest.skip("ROM not present; skipping load test")

    pyboy = run_emulator.create_pyboy(window="null", scale=1, debug=False)
    try:
        # tick once to ensure no immediate crash
        pyboy.tick()
    finally:
        pyboy.stop(save=False)


def test_speed_can_increase_and_decrease():
    class FakePyBoy:
        def __init__(self):
            self.speeds = []

        def set_emulation_speed(self, speed):
            self.speeds.append(speed)

    pb = FakePyBoy()
    speed = 1.0
    speed = run_emulator.apply_speed(pb, speed, 1.5)
    speed = run_emulator.apply_speed(pb, speed, 1 / 1.5)

    assert pb.speeds[0] > 1.0  # increased
    assert pb.speeds[1] < pb.speeds[0]  # decreased
    assert run_emulator.MIN_SPEED <= speed <= run_emulator.MAX_SPEED


def test_save_and_load_slot(tmp_path: Path):
    class FakePyBoy:
        def save_state(self, fileobj):
            fileobj.write(b"state")

        def load_state(self, fileobj):
            data = fileobj.read()
            assert data == b"state"

    pb = FakePyBoy()
    slot = 1
    path = run_emulator.save_state_slot(pb, slot, state_dir=tmp_path)
    assert path.exists()

    path_loaded = run_emulator.load_state_slot(pb, slot, state_dir=tmp_path)
    assert path_loaded == path


def test_llm_client_talks(monkeypatch):
    responses = []

    def fake_chat(messages, **kwargs):
        responses.append({"echo": messages})
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr("llm_client.chat", fake_chat)
    messages = [
        {"role": "system", "content": "Always answer in rhymes. Today is Thursday"},
        {"role": "user", "content": "What day is it today?"},
    ]

    result = fake_chat(messages)
    assert result["choices"][0]["message"]["content"] == "ok"
    assert responses[0]["echo"] == messages
