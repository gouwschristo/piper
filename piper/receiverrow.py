# SPDX-License-Identifier: GPL-2.0-or-later

from gettext import gettext as _

import gi

from .pairingdialog import PairingDialog
from .ratbagd import RatbagdReceiver

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango  # noqa: E402


class ReceiverRow(Gtk.Box):
    """One row per Logitech receiver: what is paired and how to add another."""

    __gtype_name__ = "ReceiverRow"

    def __init__(self, receiver: RatbagdReceiver, *args, **kwargs) -> None:
        Gtk.Box.__init__(self, *args, **kwargs)
        self._receiver = receiver

        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_spacing(12)

        self._label = Gtk.Label(xalign=0)
        self._label.set_line_wrap(True)
        self._label.set_ellipsize(Pango.EllipsizeMode.END)
        self._label.set_max_width_chars(36)
        self._label.set_hexpand(True)
        self.pack_start(self._label, True, True, 0)

        self._button = Gtk.Button(label=_("Pair…"))
        self._button.set_valign(Gtk.Align.CENTER)
        self._button.connect("clicked", self._on_pair_clicked)
        self.pack_start(self._button, False, False, 0)

        self.refresh()

    def refresh(self) -> None:
        try:
            devices = self._receiver.get_devices()
        except Exception:  # the receiver may have been unplugged
            devices = []

        if devices:
            names = ", ".join(name for _, name, _, _ in devices)
            text = _("%s — %d device(s) paired: %s") % (
                _("Logitech receiver"),
                len(devices),
                names,
            )
        else:
            text = _("%s — no devices paired") % _("Logitech receiver")

        firmware = self._receiver.firmware_version
        if firmware:
            text = f"{text}\n" + _("Firmware %s") % firmware
        self._label.set_label(text)

    def _on_pair_clicked(self, button: Gtk.Button) -> None:
        dialog = PairingDialog(self._receiver, self.get_toplevel())
        dialog.connect("destroy", lambda _: self.refresh())
        dialog.show()
