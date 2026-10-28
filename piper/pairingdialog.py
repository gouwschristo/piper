# SPDX-License-Identifier: GPL-2.0-or-later

from gettext import gettext as _

import gi

from .ratbagd import RatbagdReceiver

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

# The receiver's own firmware expires the window; keep the two in step.
PAIRING_TIMEOUT = 30


class PairingDialog(Gtk.Dialog):
    """Opens a receiver's pairing window and shows what is paired to it.

    A receiver pairs a device on its own once the window is open: the device has
    to be switched off and on again (or put into pairing mode) while the window
    lasts. This dialog therefore only reports, it never pairs anything itself.
    """

    __gtype_name__ = "PairingDialog"

    def __init__(self, receiver: RatbagdReceiver, parent: Gtk.Window) -> None:
        Gtk.Dialog.__init__(
            self,
            title=_("Pair a device"),
            transient_for=parent,
            modal=True,
            use_header_bar=True,
        )
        self._receiver = receiver
        self._remaining = PAIRING_TIMEOUT
        self._initial_count = len(receiver.get_devices())
        self._timer_id = 0
        self._started = False

        self.add_button(_("Stop pairing"), Gtk.ResponseType.CLOSE)
        self.set_default_size(420, -1)

        box = self.get_content_area()
        box.set_spacing(12)
        box.set_border_width(12)

        self._status = Gtk.Label(xalign=0)
        self._status.set_line_wrap(True)
        self._status.set_max_width_chars(60)
        box.pack_start(self._status, False, False, 0)

        hint = Gtk.Label(
            label=_(
                "Switch the device off and on again while this window is open. "
                "The receiver pairs it on its own; nothing is written to any "
                "profile."
            ),
            xalign=0,
        )
        hint.set_line_wrap(True)
        hint.set_max_width_chars(60)
        hint.get_style_context().add_class("dim-label")
        box.pack_start(hint, False, False, 0)

        self._listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._listbox.set_header_func(self._add_row_header)
        frame = Gtk.Frame(shadow_type=Gtk.ShadowType.IN)
        frame.add(self._listbox)
        box.pack_start(frame, True, True, 0)

        self.connect("response", self._on_response)
        self.connect("destroy", self._on_destroy)

        self._start()

    def _start(self) -> None:
        try:
            self._receiver.open_pairing_window(PAIRING_TIMEOUT)
        except GLib.Error as e:
            self._status.set_markup(
                _("Could not open the pairing window: %s") % e.message
            )
            return

        self._started = True
        self._update()
        self._timer_id = GLib.timeout_add_seconds(1, self._on_tick)

    def _stop(self) -> None:
        # Called from the response handler and again from destroy(), so it has
        # to be idempotent: closing a window that is not open is an error on the
        # bus and would be logged for no reason.
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = 0
        if not self._started:
            return
        self._started = False
        self._receiver.close_pairing_window()

    def _on_tick(self) -> bool:
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer_id = 0
            self._update(final=True)
            return False
        self._update()
        return True

    def _on_response(self, dialog: Gtk.Dialog, response: int) -> None:
        self._stop()
        self.destroy()

    def _on_destroy(self, widget: Gtk.Widget) -> None:
        self._stop()

    @staticmethod
    def _add_row_header(row: Gtk.ListBoxRow, before: Gtk.ListBoxRow) -> None:
        if before is None:
            row.set_header(None)
        else:
            row.set_header(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

    def _update(self, final: bool = False) -> None:
        try:
            devices = self._receiver.get_devices()
        except GLib.Error:
            devices = []

        if final:
            self._status.set_markup(_("The pairing window has closed."))
        elif len(devices) > self._initial_count:
            self._status.set_markup(
                _("Paired. %d device(s) connected.") % len(devices)
            )
        else:
            self._status.set_markup(
                _("Listening for a new device… %d s left.") % self._remaining
            )

        self._listbox.foreach(Gtk.Widget.destroy)
        if not devices:
            self._listbox.add(
                Gtk.Label(label=_("Nothing is paired to this receiver."), xalign=0)
            )
        for index, name, kind, serial in devices:
            label = Gtk.Label(
                label=f"{name} ({kind}) — {_('slot')} {index + 1}, "
                f"serial 0x{serial:08X}",
                xalign=0,
            )
            self._listbox.add(label)
        self._listbox.show_all()
