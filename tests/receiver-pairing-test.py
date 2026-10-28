#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the receiver row and the pairing dialog.

A receiver is not a configurable device: it reports which devices are paired and
can arm a pairing window. Neither may touch the device's profiles, and the
dialog must close the window exactly once however it is dismissed.

Exits 77 (meson: SKIP) without a display.
"""
import os
import sys

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GObject, Gtk
except (ImportError, ValueError) as e:  # pragma: no cover
    print(f"gtk bindings unavailable: {e}")
    sys.exit(77)

if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    print("no display available")
    sys.exit(77)

try:
    Gtk.init_check()
except Exception:  # pragma: no cover
    sys.exit(77)

DATA = os.environ.get("PIPER_PKGDATADIR", "/usr/local/share/piper")
Gio.Resource._register(Gio.resource_load(os.path.join(DATA, "piper.gresource")))

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import piper.pairingdialog as pd  # noqa: E402
import piper.receiverrow as rr  # noqa: E402
import piper.welcomeperspective as wp  # noqa: E402


class FakeReceiver(GObject.Object):
    def __init__(self, devices=None, firmware="7.2.B0017"):
        super().__init__()
        if devices is None:
            devices = [(0, "PRO X 2", "mouse", 0x58652404)]
        self._devices = devices
        self._firmware = firmware
        self.opened = []
        self.closed = 0

    def get_devices(self):
        return list(self._devices)

    def open_pairing_window(self, timeout=30):
        self.opened.append(timeout)

    def close_pairing_window(self):
        self.closed += 1

    @GObject.Property(type=str)
    def firmware_version(self):
        return self._firmware

    @GObject.Property(type=bool, default=False)
    def pairing_open(self):
        return bool(self.opened) and self.closed == 0


# The row summarises what is paired and shows the receiver's own firmware.
receiver = FakeReceiver()
row = rr.ReceiverRow(receiver)
text = row._label.get_label()
assert "1 device(s) paired" in text, text
assert "PRO X 2" in text, text
assert "Firmware 7.2.B0017" in text, text

# A receiver with nothing paired says so rather than showing an empty list.
empty = rr.ReceiverRow(FakeReceiver(devices=[]))
assert "no devices paired" in empty._label.get_label(), empty._label.get_label()

# The welcome perspective only shows the receiver section when there is one.
perspective = wp.WelcomePerspective()
perspective.set_receivers([])
assert not perspective.frame_receivers.get_visible(), "empty receiver section shown"
assert perspective.box_receivers.get_children() == []
perspective.set_receivers([receiver])
assert perspective.frame_receivers.get_visible()
assert len(perspective.box_receivers.get_children()) == 1

# The dialog arms one window for the whole timeout and lists what is paired.
dialog = rr.PairingDialog(receiver, None)
assert receiver.opened == [pd.PAIRING_TIMEOUT], receiver.opened
assert "Listening for a new device" in dialog._status.get_text(), (
    dialog._status.get_text()
)
listed = [c.get_child().get_text() for c in dialog._listbox.get_children()]
assert any("PRO X 2" in text for text in listed), listed
assert any("0x58652404" in text for text in listed), listed

# Dismissing it closes the window exactly once, even though both the response
# handler and destroy() call the same stop path.
dialog._stop()
assert receiver.closed == 1, receiver.closed
dialog.destroy()
assert receiver.closed == 1, "pairing window closed twice"

# A second device appearing in the window is reported as a success, not as
# another second left.
new_device = rr.PairingDialog(receiver, None)
receiver._devices = list(receiver._devices) + [(1, "MX Anywhere", "mouse", 0x11223344)]
new_device._update()
assert new_device._status.get_text().startswith("Paired."), (
    new_device._status.get_text()
)
new_device._stop()
new_device.destroy()

# When the window runs out the dialog says so and stops counting.
final = rr.PairingDialog(receiver, None)
final._remaining = 1
final._on_tick()
assert final._status.get_text() == "The pairing window has closed.", (
    final._status.get_text()
)
final.destroy()

print("receiver pairing: OK")
