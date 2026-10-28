#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the extended profile fields on the advanced page.

BHOP timeout, power-save/power-off timeouts and the shift resolution are stored
in the onboard profile and exposed by ratbagd as writable properties. A device
without them reports -1 and must get a disabled control, never a write.

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
import piper.advancedpage as ap  # noqa: E402


class FakeResolution:
    def __init__(self, index):
        self.index = index
        self.resolution = (100 * (index + 1), 100 * (index + 1))


class FakeProfile(GObject.Object):
    debounce = 0
    debounces = [0, 4, 8]
    angle_snapping = -1
    report_rates = [125, 1000, 4000]
    report_rate = 4000

    def __init__(self, bhop=0, save=60, off=300, shift=0, supported=True):
        super().__init__()
        self.resolutions = [FakeResolution(i) for i in range(3)]
        self._bhop = bhop if supported else -1
        self._save = save if supported else -1
        self._off = off if supported else -1
        self._shift = shift if supported else -1

    @GObject.Property(type=int)
    def bhop_timeout(self):
        return self._bhop

    @bhop_timeout.setter
    def bhop_timeout(self, value):
        self._bhop = value
        self.notify("bhop-timeout")

    @GObject.Property(type=int)
    def power_save_timeout(self):
        return self._save

    @power_save_timeout.setter
    def power_save_timeout(self, value):
        self._save = value
        self.notify("power-save-timeout")

    @GObject.Property(type=int)
    def power_off_timeout(self):
        return self._off

    @power_off_timeout.setter
    def power_off_timeout(self, value):
        self._off = value
        self.notify("power-off-timeout")

    @GObject.Property(type=int)
    def shift_resolution(self):
        return self._shift

    @shift_resolution.setter
    def shift_resolution(self, value):
        self._shift = value
        self.notify("shift-resolution")


class StubMap(Gtk.Box):
    def __init__(self, *a, **k):
        Gtk.Box.__init__(self)


ap.MouseMap = StubMap

profile = FakeProfile(bhop=0, save=60, off=300, shift=2)
page = ap.AdvancedPage(None, profile)

# BHOP: "Off" plus 100..1000 ms
bhop = [row[0] for row in page.bhop_timeout.get_model()]
assert bhop == [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000], bhop
assert page._combo_value(page.bhop_timeout) == 0

# selecting 300 ms must reach the profile
idx = bhop.index(300)
page.bhop_timeout.set_active(idx)
assert profile.bhop_timeout == 300, profile.bhop_timeout

# power timeouts reflect the device value and write through
assert page._combo_value(page.power_save_timeout) == 60
page.power_save_timeout.set_active(
    [r[0] for r in page.power_save_timeout.get_model()].index(120)
)
assert profile.power_save_timeout == 120, profile.power_save_timeout
assert page._combo_value(page.power_off_timeout) == 300

# shift resolution lists the profile's resolutions
shift = page.shift_resolution.get_model()
assert page.shift_resolution.get_active() >= 0
assert page._combo_value(page.shift_resolution) == 2

# an external change (from ratbagctl, say) updates the widget
profile.bhop_timeout = 500
assert page._combo_value(page.bhop_timeout) == 500

# a device without the fields gets disabled controls
unsupported = FakeProfile(supported=False)
page2 = ap.AdvancedPage(None, unsupported)
for combo in (
    page2.bhop_timeout,
    page2.power_save_timeout,
    page2.power_off_timeout,
    page2.shift_resolution,
):
    assert not combo.get_sensitive(), "control enabled for an unsupported field"

print("advanced page extended fields: OK")
