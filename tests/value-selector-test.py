#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check that a value selector always shows every option.

The dropdowns used to be GtkComboBox, whose popup is a GtkMenu: on Wayland the
compositor could hand back a menu a few pixels shorter than its content, and GTK
then made it scrollable, clipping the first and last entries. These assertions
lock in the replacement: a popover that is at least as tall as its list and
contains no scrolling widget at all.

Exits 77 (meson: SKIP) without a display.
"""
import os
import sys

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, Gtk
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from piper.util.valueselector import ValueSelector  # noqa: E402


def pump(iterations=30, delay=0.02):
    import time

    for _ in range(iterations):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(delay)


def contains_scrolled_window(widget):
    if isinstance(widget, Gtk.ScrolledWindow):
        return True
    if isinstance(widget, Gtk.Container):
        return any(contains_scrolled_window(c) for c in widget.get_children())
    return False


ENTRIES = [(0, "Off")] + [(ms, f"{ms} ms") for ms in range(100, 1001, 100)]


# --- values, without a window
selector = ValueSelector()
selector.set_entries(ENTRIES)
assert selector.get_active_id() == "0", selector.get_active_id()
assert selector.get_active_text() == "Off", selector.get_active_text()
assert len(selector.get_entries()) == 11

changes = []
selector.connect("changed", lambda s: changes.append(s.get_active_id()))

selector.set_active_id("300")
assert selector.get_active_id() == "300"
assert selector.get_active_text() == "300 ms", selector.get_active_text()
assert selector.get_active() == 3, selector.get_active()
assert changes == ["300"], changes

# setting the same value again must not emit
selector.set_active_id("300")
assert changes == ["300"], changes

# a value the list does not offer clears the selection rather than lying
selector.set_active_id("250")
assert selector.get_active_id() is None, selector.get_active_id()
assert selector.get_active_text() is None
assert selector.get_active() == -1

selector.set_active(1)
assert selector.get_active_id() == "100", selector.get_active_id()

# --- the popup, with a window so it can be measured
window = Gtk.Window()
window.add(selector)
window.set_default_size(360, 620)
window.show_all()
pump(60)

popover = selector.get_popover()
assert popover is not None
assert not contains_scrolled_window(popover), (
    "the value list contains a scrolled window, so options can be hidden"
)

popover.popup()
pump(40)
listbox = popover.get_child()
natural_height = listbox.get_preferred_height()[1]
allocated_height = popover.get_allocated_height()

assert len(listbox.get_children()) == len(ENTRIES), len(listbox.get_children())
assert all(row.get_visible() for row in listbox.get_children()), (
    "a row is not visible in the open popup"
)
assert allocated_height >= natural_height, (
    f"popup is {allocated_height}px for {natural_height}px of rows: it would scroll"
)

# The popup is anchored to the control and is at least as wide, so it reads as
# this control's list instead of a narrow stray menu.
assert popover.get_allocated_width() >= selector.get_allocated_width(), (
    f"popup is {popover.get_allocated_width()}px wide for a "
    f"{selector.get_allocated_width()}px control"
)

# activating a row writes the value and closes the popup
target = [row for row in listbox.get_children() if row.value == 600][0]
listbox.emit("row-activated", target)
pump(20)
assert selector.get_active_id() == "600", selector.get_active_id()
assert not popover.get_visible(), "popup stayed open after a selection"

window.destroy()
print("value selector: OK")
