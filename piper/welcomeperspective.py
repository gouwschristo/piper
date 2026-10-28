# SPDX-License-Identifier: GPL-2.0-or-later

from typing import List, Optional

from .devicerow import DeviceRow
from .ratbagd import RatbagdDevice, RatbagdReceiver
from .receiverrow import ReceiverRow

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk  # noqa


@Gtk.Template(resource_path="/org/freedesktop/Piper/ui/WelcomePerspective.ui")
class WelcomePerspective(Gtk.Box):
    """A perspective to present a list of devices for the user to pick one to
    configure."""

    __gtype_name__ = "WelcomePerspective"

    __gsignals__ = {
        "device-selected": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),
    }

    box_receivers: Gtk.Box = Gtk.Template.Child()  # type: ignore
    frame_receivers: Gtk.Frame = Gtk.Template.Child()  # type: ignore
    listbox: Gtk.ListBox = Gtk.Template.Child()  # type: ignore
    _titlebar: Gtk.HeaderBar = Gtk.Template.Child()  # type: ignore

    def __init__(self, *args, **kwargs) -> None:
        """Instantiates a new WelcomePerspective."""
        Gtk.Box.__init__(self, *args, **kwargs)
        self.listbox.set_sort_func(self._listbox_sort_func)
        self.listbox.set_header_func(self._listbox_header_func)

    def set_receivers(self, receivers: List[RatbagdReceiver]) -> None:
        """Sets the receivers to present below the device list.

        @param receivers The receivers to present, as [ratbagd.RatbagdReceiver]
        """
        for child in self.box_receivers.get_children():
            child.destroy()
        for receiver in receivers:
            self.box_receivers.pack_start(ReceiverRow(receiver), False, False, 0)

        # A receiver is only worth showing when it is a receiver: hide the whole
        # section when there is none, so the page stays a device picker.
        self.frame_receivers.set_no_show_all(not receivers)
        self.frame_receivers.set_visible(bool(receivers))
        self.box_receivers.show_all()

    def set_devices(self, devices: List[RatbagdDevice]) -> None:
        """Sets the devices to present to the user.

        @param devices The devices to present, as [ratbagd.RatbagdDevice]
        """
        self.listbox.foreach(Gtk.Widget.destroy)
        for device in devices:
            self.add_device(device)

    def add_device(self, device: RatbagdDevice) -> None:
        """Add a device to the list.

        @param device The device to add, as ratbagd.RatbagdDevice
        """
        self.listbox.add(DeviceRow(device))

    def remove_device(self, device: RatbagdDevice) -> None:
        """Remove a device from the list.

        @param device The device to remove, as ratbagd.RatbagdDevice
        """
        for child in self.listbox.get_children():
            if child._device is device:
                child.destroy()
                break

    @GObject.Property
    def name(self) -> str:
        """The name of this perspective."""
        return "welcome_perspective"

    @GObject.Property
    def titlebar(self) -> Gtk.Widget:
        """The titlebar to this perspective."""
        return self._titlebar

    @GObject.Property
    def can_go_back(self) -> bool:
        """Whether this perspective wants a back button to be displayed in case
        there is more than one connected device."""
        return False

    @GObject.Property
    def can_shutdown(self) -> bool:
        """Whether this perspective can safely shutdown."""
        return True

    @Gtk.Template.Callback("_on_device_row_activated")
    def _on_device_row_activated(self, listbox: Gtk.ListBox, row: DeviceRow) -> None:
        self.emit("device-selected", row.device)

    def _listbox_sort_func(self, row1: DeviceRow, row2: DeviceRow) -> int:
        name1 = row1.device.name.casefold()
        name2 = row2.device.name.casefold()
        if name1 < name2:
            return -1
        if name1 == name2:
            return 0
        return 1

    def _listbox_header_func(
        self, row: Gtk.ListBoxRow, before: Optional[Gtk.ListBoxRow]
    ) -> None:
        if before is not None:
            separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            row.set_header(separator)
