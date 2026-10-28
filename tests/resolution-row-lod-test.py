#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check that a resolution row edits its own lift-off distance.

LOD is stored per resolution (each DPI stage carries its own value), so it must
live on the resolution row rather than as a profile-wide setting. Devices whose
driver does not advertise RATBAG_RESOLUTION_CAP_LOD must not see the control.

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
from piper.ratbagd import RatbagdResolution  # noqa: E402
from piper.resolutionrow import ResolutionRow  # noqa: E402


class FakeResolution(GObject.Object):
    capabilities = [RatbagdResolution.CAP_LOD]

    def __init__(self, lod=2):
        super().__init__()
        self._lod = lod
        self.resolutions = [100, 200, 400, 800, 1600]
        self.resolution = (400, 400)
        self.is_active = True
        self.is_default = True
        self.is_disabled = False

    @GObject.Property(type=object)
    def lod(self):
        return self._lod

    @lod.setter
    def lod(self, value):
        if value != self._lod:
            self._lod = value
            self.notify("lod")


class Page:
    """Stands in for ResolutionsPage."""


row = ResolutionRow(FakeResolution(2), Page())
model = row.lod.get_model()
labels = [r[1] for r in model]
assert labels == ["Low", "Medium", "High"], labels

idx = row.lod.get_active()
assert idx >= 0, "no LOD selected for a value the device reports"
assert int(model[idx][0]) == 2, f"selected {model[idx][0]}, expected the device value 2"

# Selecting High must be written through to the resolution.
row.lod.set_active(2)
assert row._resolution.lod == 3, row._resolution.lod
assert row.lod_box.get_visible()

# The control must be real: it sits on its own line in the expandable area (it
# used to be squeezed into the narrow, homogeneous button row where it collapsed
# to nothing) and must request a usable width.
parent = row.lod.get_parent()
while parent is not None and parent is not row:
    parent = parent.get_parent()
assert row.lod_box.get_parent() is not None
assert row.lod_box.get_parent() is not row.disable_button.get_parent(), (
    "LOD control is back inside the button row, where it gets squeezed"
)
min_w, natural_w = row.lod.get_preferred_width()
assert natural_w > 0, "LOD combo requests no space at all"

# A driver without the capability must hide the control entirely.
class NoLod(FakeResolution):
    capabilities = [RatbagdResolution.CAP_DISABLE]


row2 = ResolutionRow(NoLod(0), Page())
assert not row2.lod_box.get_visible(), "LOD control shown without the capability"

print("resolution row LOD: OK")
