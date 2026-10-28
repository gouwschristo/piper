# SPDX-License-Identifier: GPL-2.0-or-later
"""A value selector that always shows every option.

GtkComboBox puts its choices in a GtkMenu. On Wayland that menu is negotiated
with the compositor and can come back a few pixels shorter than its content, at
which point GTK marks it scrollable: up/down arrows appear, the active row is
centred, and the first and last entries get clipped. There is no supported way to
tell a combo "never do that".

This widget uses a GtkPopover holding a GtkListBox instead. The popover is sized
from its child's natural size and contains no GtkScrolledWindow, so there is
nothing to scroll and every option is visible at once.

The API mirrors the parts of GtkComboBox that Piper used (get_active_id,
set_active_id, get_active_text, get_active, plus a "changed" signal that
handler_block works on), so pages do not need to know which widget they talk to.
Values are integers, matching the profile.
"""

from typing import List, Optional, Tuple

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GObject, Gtk, Pango  # noqa: E402


class ValueSelector(Gtk.MenuButton):
    """A button showing the current value; clicking it lists every option."""

    __gtype_name__ = "PiperValueSelector"

    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, *args, **kwargs) -> None:
        Gtk.MenuButton.__init__(self, *args, **kwargs)

        self._entries: List[Tuple[int, str]] = []
        self._value: Optional[int] = None

        self._label = Gtk.Label(xalign=0)
        # Ellipsized labels report a minimum width of ~0, which lets the whole
        # button collapse to just its arrow in a narrow column (the LOD control
        # in a resolution row). width-chars is a floor, so the value stays
        # readable and the button keeps a usable minimum size.
        self._label.set_width_chars(7)
        self._label.set_ellipsize(Pango.EllipsizeMode.END)
        self._box = Gtk.Box(spacing=6)
        self._box.pack_start(self._label, True, True, 0)
        self._box.pack_start(
            Gtk.Image.new_from_icon_name("pan-down-symbolic", Gtk.IconSize.BUTTON),
            False,
            False,
            0,
        )
        self.add(self._box)

        self._listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._listbox.connect("row-activated", self._on_row_activated)

        # Deliberately no GtkScrolledWindow: the popover takes the height of the
        # list, so no option can end up scrolled out of sight.
        popover = Gtk.Popover()
        popover.add(self._listbox)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.connect("show", self._on_popover_shown)
        self.set_popover(popover)

        # These children are built in code, so they start hidden and would only
        # appear if an ancestor happened to call show_all(). Not every container
        # does (a resolution row does not), so show them here.
        self._box.show_all()

    # -- the GtkComboBox-alike surface

    def set_entries(self, entries: List[Tuple[int, str]]) -> None:
        """Replace the options, keeping the current value when it still exists."""
        previous = self._value

        self._entries = list(entries)
        self._listbox.foreach(Gtk.Widget.destroy)
        for value, label in self._entries:
            row = Gtk.ListBoxRow()
            row.value = value
            cell = Gtk.Label(label=label, xalign=0)
            cell.set_margin_start(6)
            cell.set_margin_end(6)
            cell.set_margin_top(4)
            cell.set_margin_bottom(4)
            row.add(cell)
            self._listbox.add(row)
        self._listbox.show_all()

        if previous is not None and self._has(previous):
            self._set_value(previous)
        elif self._entries:
            self._set_value(self._entries[0][0])
        else:
            self._set_value(None)

    def get_active_id(self) -> Optional[str]:
        return None if self._value is None else str(self._value)

    def set_active_id(self, active_id) -> None:
        if active_id in (None, ""):
            self._set_value(None)
            return
        value = int(active_id)
        self._set_value(value if self._has(value) else None)

    def get_active_text(self) -> Optional[str]:
        for value, label in self._entries:
            if value == self._value:
                return label
        return None

    def set_active(self, index: int) -> None:
        """Select by position, like GtkComboBox.set_active(); -1 clears."""
        if index is None or index < 0 or index >= len(self._entries):
            self._set_value(None)
        else:
            self._set_value(self._entries[index][0])

    def get_active(self) -> int:
        for index, (value, _) in enumerate(self._entries):
            if value == self._value:
                return index
        return -1

    def get_entries(self) -> List[Tuple[int, str]]:
        return list(self._entries)

    # -- internals

    def _has(self, value: int) -> bool:
        return any(value == v for v, _ in self._entries)

    def _set_value(self, value: Optional[int]) -> None:
        changed = value != self._value
        self._value = value
        self._label.set_text(self.get_active_text() or "")
        if changed:
            self.emit("changed")

    def _on_popover_shown(self, popover: Gtk.Popover) -> None:
        # Match the popover to the control and anchor it exactly underneath, so
        # it reads as this control's list rather than a stray menu.
        width = self.get_allocated_width()
        if width > 0:
            rect = Gdk.Rectangle()
            rect.x = 0
            rect.y = 0
            rect.width = width
            rect.height = max(self.get_allocated_height(), 1)
            popover.set_pointing_to(rect)
            popover.set_position(Gtk.PositionType.BOTTOM)
            popover.set_size_request(width, -1)

        # Mark the selected row so the list opens showing where you are. Every
        # row is visible anyway, so this never scrolls anything.
        for row in self._listbox.get_children():
            context = row.get_style_context()
            context.remove_class("suggested-action")
            if getattr(row, "value", None) == self._value:
                context.add_class("suggested-action")

    def _on_row_activated(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        popover = self.get_popover()
        if popover is not None:
            popover.popdown()
        value = getattr(row, "value", None)
        if value is not None:
            self.set_active_id(str(value))
