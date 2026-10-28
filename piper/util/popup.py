# SPDX-License-Identifier: GPL-2.0-or-later
"""Workaround for combo popups that open too short on Wayland.

GTK sizes a combo's popup from the rows it has measured. On Wayland the popup
geometry is negotiated with the compositor, and the first negotiation can leave
the menu shorter than its content: the list then opens with a scrollbar and only
grows once something inside it forces a re-measure (scrolling does exactly
that). Re-requesting the size as soon as the popup is shown reproduces that
re-measure without the user having to touch anything.

Measured on this machine (KDE Plasma 6, Wayland): a programmatic popup already
gets its full height, so this only matters for the pointer-driven path, which
cannot be scripted. It is cheap, it does nothing when the popup is already the
right size, and it is a no-op on X11.
"""

from typing import Set

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

_resizing: Set[Gtk.Widget] = set()


def _on_popup_shown(combo: Gtk.ComboBox, _pspec=None) -> None:
    if not combo.get_property("popup-shown"):
        return
    if combo in _resizing:
        return

    _resizing.add(combo)
    try:
        for menu in Gtk.Menu.get_for_attach_widget(combo):
            _width = menu.get_allocated_width()
            _min_h, natural_h = menu.get_preferred_height()
            if natural_h > menu.get_allocated_height():
                menu.resize(_width, natural_h)
    finally:
        _resizing.discard(combo)


def ensure_popup_sized(combo: Gtk.ComboBox) -> None:
    """Re-measure a combo's popup every time it opens."""
    combo.connect("notify::popup-shown", _on_popup_shown)
