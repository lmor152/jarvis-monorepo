"""
SatelliteState manages the assistant's physical and logical states.
This is where you can control LEDs, fans, or display indicators.
"""

import time
from typing import Literal

State = Literal["idle", "listening", "speaking", "thinking"]


class SatelliteState:
    def __init__(self):
        self.mode: State = "idle"
        self.last_state_change = time.time()

    # --------------------------------------------------------
    # Core state management
    # --------------------------------------------------------

    def set_state(self, new_state: State):
        if new_state not in ["idle", "listening", "speaking", "thinking"]:
            raise ValueError(f"Invalid state: {new_state}")

        self.mode = new_state
        self.last_state_change = time.time()

        # You can add transitions here
        if new_state == "thinking":
            self.set_state_thinking()
        elif new_state == "listening":
            self.set_state_listening()
        elif new_state == "speaking":
            self.set_state_speaking()
        else:
            self.set_state_idle()

    def set_state_idle(self):
        pass

    def set_state_listening(self):
        pass

    def set_state_speaking(self):
        pass

    def set_state_thinking(self):
        pass

    # --------------------------------------------------------
    # Hardware control stubs 
    # --------------------------------------------------------

    def set_led(self, state: bool, color: str = "white"):
        """Turns LEDs on/off with a given color (stub implementation)."""
        self.led_on = state
        if state:
            print(f"💡 LED ON ({color})")
        else:
            print("💡 LED OFF")

    def play_sound(self, name: str):
        """Play a sound effect (stub)."""
        print(f"🔊 Playing sound: {name}")

    def display_text(self, text: str):
        """Show text on a display or console."""
        print(f"📟 Display: {text}")

    # --------------------------------------------------------
    # Helper methods
    # --------------------------------------------------------

    def is_idle(self):
        return self.mode == "idle"

    def is_active(self):
        return self.mode in ["listening", "speaking"]
