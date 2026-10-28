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


class FakeResolution(GObject.Object):
    capabilities = [3]  # RatbagdResolution.CAP_LOD

    def __init__(self, index, active=False, lod=2):
        super().__init__()
        self.index = index
        self.resolution = (100 * (index + 1), 100 * (index + 1))
        self.is_active = active
        self.is_default = index == 0
        self._lod = lod

    @GObject.Property(type=object)
    def lod(self):
        return self._lod

    @lod.setter
    def lod(self, value):
        if value != self._lod:
            self._lod = value
            self.notify("lod")


class FakeProfile(GObject.Object):
    debounce = 0
    debounces = [0, 4, 8]
    angle_snapping = -1
    report_rates = [125, 1000, 4000]
    report_rate = 4000

    def __init__(self, bhop=0, save=60, off=300, shift=0, supported=True):
        super().__init__()
        self.resolutions = [FakeResolution(i, active=(i == 1), lod=2) for i in range(3)]
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


class FakeDevice(GObject.Object):
    def __init__(self, onboard=True, supported=True):
        super().__init__()
        self._onboard = onboard
        self._supported = supported

    @GObject.Property(type=bool, default=False)
    def has_onboard_mode_capability(self):
        return self._supported

    @GObject.Property(type=bool, default=False)
    def onboard_mode(self):
        return self._onboard

    @onboard_mode.setter
    def onboard_mode(self, value):
        if value != self._onboard:
            self._onboard = value
            self.notify("onboard-mode")


class StubMap(Gtk.Box):
    def __init__(self, *a, **k):
        Gtk.Box.__init__(self)


ap.MouseMap = StubMap

profile = FakeProfile(bhop=0, save=60, off=300, shift=2)
page = ap.AdvancedPage(None, profile)

# BHOP: "Off" plus 100..1000 ms
bhop = [value for value, _ in page._combo_entries[page.bhop_timeout]]
assert bhop == [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000], bhop
assert page._combo_value(page.bhop_timeout) == 0

# selecting 300 ms must reach the profile
idx = bhop.index(300)
page.bhop_timeout.set_active(idx)
assert profile.bhop_timeout == 300, profile.bhop_timeout

# power timeouts reflect the device value and write through
assert page._combo_value(page.power_save_timeout) == 60
page.power_save_timeout.set_active_id("120")
assert profile.power_save_timeout == 120, profile.power_save_timeout
assert page._combo_value(page.power_off_timeout) == 300

# shift resolution lists the profile's resolutions
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

# Lift-off distance is shown for the *active* stage of this profile, with the
# profile dependence called out in the UI.
profile3 = FakeProfile()
page3 = ap.AdvancedPage(None, profile3)
lod_labels = [label for _, label in page3._combo_entries[page3.lod]]
assert lod_labels == ["Low", "Medium", "High"], lod_labels
assert page3._combo_value(page3.lod) == 2
assert page3.lod_note.get_visible()
assert "profile" in page3.lod_note.get_label().lower()

page3.lod.set_active(2)                       # High
assert profile3.resolutions[1].lod == 3, profile3.resolutions[1].lod
assert profile3.resolutions[0].lod == 2, "inactive stage must not change"

# An external change to the active stage updates the control.
profile3.resolutions[1].lod = 1
assert page3._combo_value(page3.lod) == 1

# A profile whose active stage has no LOD control disables the row and hides
# the explanation rather than showing a dead setting.
class NoLodResolution(FakeResolution):
    capabilities = []

    def __init__(self, index, active=False):
        super().__init__(index, active)


nolod = FakeProfile()
nolod.resolutions = [NoLodResolution(i, active=(i == 0)) for i in range(3)]
page4 = ap.AdvancedPage(None, nolod)
assert not page4.lod.get_sensitive()
assert not page4.lod_note.get_visible()

# Device mode is a device-wide toggle, not a profile value: it must be offered
# only when the device reports the capability, and changing it must reach the
# device immediately rather than waiting for a commit.
device = FakeDevice(onboard=True)
page5 = ap.AdvancedPage(device, FakeProfile())
assert page5.device_mode_row.get_visible(), "mode row hidden for a capable device"
assert page5.device_mode_note.get_visible()
mode = [value for value, _ in page5._combo_entries[page5.device_mode]]
assert mode == [1, 0], mode
assert page5._combo_value(page5.device_mode) == 1

page5.device_mode.set_active(mode.index(0))       # Host (software) control
assert device.onboard_mode is False, device.onboard_mode

# An external change (from ratbagctl, say) updates the control.
device.onboard_mode = True
assert page5._combo_value(page5.device_mode) == 1

# A device without the switch must not show a dead row.
page6 = ap.AdvancedPage(FakeDevice(supported=False), FakeProfile())
assert not page6.device_mode_row.get_visible()
assert not page6.device_mode_note.get_visible()

print("advanced page extended fields: OK")
