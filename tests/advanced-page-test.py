#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check that AdvancedPage builds its report-rate list from the profile.

The page used to hardcode four radio buttons (125/250/500/1000 Hz). Devices that
report more rates -- LIGHTSPEED mice expose up to 8000 Hz -- could not be
represented: no button was selected, and choosing one silently downgraded the
profile to 1000 Hz or less. This test locks in the dynamic behaviour.

Exits 77 (meson: SKIP) when no display is available, since Gtk needs one.
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
    print("cannot connect to a display")
    sys.exit(77)

DATA = os.environ.get("PIPER_PKGDATADIR", "/usr/local/share/piper")
res = Gio.resource_load(os.path.join(DATA, "piper.gresource"))
Gio.Resource._register(res)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import piper.advancedpage as ap  # noqa: E402

RATES = [125, 250, 500, 1000, 2000, 4000, 8000]
CURRENT = 4000


class FakeProfile(GObject.Object):
    debounce = 0
    debounces = [0, 4, 8]
    angle_snapping = -1
    report_rates = RATES
    report_rate = CURRENT
    name = "fake"


class StubMap(Gtk.Box):
    """Stands in for MouseMap, which needs a real device."""

    def __init__(self, *args, **kwargs):
        Gtk.Box.__init__(self)


ap.MouseMap = StubMap

page = ap.AdvancedPage(None, FakeProfile())
labels = [row[0] for row in page.report_rate.get_model()]
assert labels == [str(r) for r in RATES], f"unexpected rates: {labels}"
assert page.report_rate.get_sensitive()

active = page.report_rate.get_active()
assert active >= 0, "no rate selected for a rate the profile reports"
assert labels[active] == str(CURRENT), f"selected {labels[active]}, expected {CURRENT}"

# Selecting another rate must be written through to the profile.
page.report_rate.set_active(RATES.index(8000))
assert page._profile.report_rate == 8000, page._profile.report_rate

# A rate the device does not report must not be presented as selected.
page._profile.report_rate = 3000
page._update_widget_report_rate()
assert page.report_rate.get_active() == -1, page.report_rate.get_active()

print("advanced page report-rate list: OK")
