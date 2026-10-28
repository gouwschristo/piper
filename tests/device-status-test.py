#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the battery indicator in the mouse perspective header.

The header shows the charge of the device itself. A device that reports no
battery (percentage -1) must not get an indicator at all, and the label must
follow later updates without the perspective being rebuilt.

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
import piper.mouseperspective as mp  # noqa: E402
from piper.ratbagd import RatbagBatteryStatus  # noqa: E402


class FakeProfile(GObject.Object):
    index = 0
    name = "Osax"
    disabled = False
    dirty = False

    def __init__(self):
        super().__init__()


class FakeDevice(GObject.Object):
    __gsignals__ = {
        "resync": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "active-profile-changed": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),
    }

    name = "Logitech PRO X 2"
    model = "usb:046d:40a9:0"

    def __init__(self, percentage=64, status=RatbagBatteryStatus.DISCHARGING):
        super().__init__()
        self._percentage = percentage
        self._status = status
        self._profile = FakeProfile()

    @GObject.Property(type=object)
    def profiles(self):
        return [self._profile]

    @property
    def active_profile(self):
        return self._profile

    @GObject.Property(type=int, default=-1)
    def battery_percentage(self):
        return self._percentage

    @battery_percentage.setter
    def battery_percentage(self, value):
        if value != self._percentage:
            self._percentage = value
            self.notify("battery-percentage")

    @GObject.Property(type=int, default=0)
    def battery_status(self):
        return int(self._status)

    @GObject.Property(type=bool, default=False)
    def has_battery(self):
        return self._percentage >= 0


perspective = mp.MousePerspective()

device = FakeDevice()
perspective._update_battery(device)
assert perspective.box_battery.get_visible(), (
    "battery hidden for a device that reports one"
)
assert perspective.label_battery.get_label() == "64%", (
    perspective.label_battery.get_label()
)
assert perspective.label_battery.get_tooltip_text() == "Running on battery"

# charging and full states get their own tooltip
perspective._update_battery(FakeDevice(status=RatbagBatteryStatus.RECHARGING))
assert perspective.label_battery.get_tooltip_text() == "Charging"
perspective._update_battery(FakeDevice(status=RatbagBatteryStatus.FULL))
assert perspective.label_battery.get_tooltip_text() == "Fully charged"
perspective._update_battery(FakeDevice(status=RatbagBatteryStatus.UNKNOWN))
assert perspective.label_battery.get_tooltip_text() == "Battery status unknown"

# an update from the device refreshes the label in place
device.battery_percentage = 40
perspective._on_device_battery_changed(device)
assert perspective.label_battery.get_label() == "40%", (
    perspective.label_battery.get_label()
)

# a device without a battery gets no indicator at all
perspective._update_battery(FakeDevice(percentage=-1))
assert not perspective.box_battery.get_visible(), (
    "battery shown for a device without one"
)

# the level icon follows the charge and the charging state
for percentage, icon in ((100, "battery-full-symbolic"), (64, "battery-good-symbolic"),
                         (40, "battery-low-symbolic"), (5, "battery-caution-symbolic")):
    perspective._update_battery(FakeDevice(percentage=percentage))
    if perspective.image_battery.get_visible():
        name = perspective.image_battery.get_icon_name()[0]
        assert name == icon, (name, icon)
perspective._update_battery(FakeDevice(status=RatbagBatteryStatus.FULL))
if perspective.image_battery.get_visible():
    assert "full-charged" in perspective.image_battery.get_icon_name()[0]
perspective._update_battery(FakeDevice(status=RatbagBatteryStatus.RECHARGING))
if perspective.image_battery.get_visible():
    assert "charging" in perspective.image_battery.get_icon_name()[0]

# The main screen must say which device is being configured.
perspective._update_device_label(device)
assert perspective.label_device.get_label() == "Logitech PRO X 2", (
    perspective.label_device.get_label()
)
assert "PRO X 2" in (perspective.label_device.get_tooltip_text() or ""), (
    perspective.label_device.get_tooltip_text()
)

print("device status header: OK")
