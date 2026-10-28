# SPDX-License-Identifier: GPL-2.0-or-later

from gettext import gettext as _
from typing import Optional

from .buttonspage import ButtonsPage
from .profilerow import ProfileRow
from .ratbagd import RatbagBatteryStatus, RatbagdDevice, RatbagdProfile
from .resolutionspage import ResolutionsPage
from .advancedpage import AdvancedPage
from .ledspage import LedsPage
from .util.gobject import connect_signal_with_weak_ref

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, GObject, Gtk  # noqa


@Gtk.Template(resource_path="/org/freedesktop/Piper/ui/MousePerspective.ui")
class MousePerspective(Gtk.Overlay):
    """The perspective to configure a mouse."""

    __gtype_name__ = "MousePerspective"

    _titlebar: Gtk.HeaderBar = Gtk.Template.Child()  # type: ignore
    add_profile_button: Gtk.Button = Gtk.Template.Child()  # type: ignore
    button_commit: Gtk.Button = Gtk.Template.Child()  # type: ignore
    button_profile: Gtk.Button = Gtk.Template.Child()  # type: ignore
    box_battery: Gtk.Box = Gtk.Template.Child()  # type: ignore
    label_device: Gtk.Label = Gtk.Template.Child()  # type: ignore
    image_battery: Gtk.Image = Gtk.Template.Child()  # type: ignore
    label_battery: Gtk.Label = Gtk.Template.Child()  # type: ignore
    label_profile: Gtk.Label = Gtk.Template.Child()  # type: ignore
    listbox_profiles: Gtk.ListBox = Gtk.Template.Child()  # type: ignore
    notification_error: Gtk.Revealer = Gtk.Template.Child()  # type: ignore
    stack: Gtk.Stack = Gtk.Template.Child()  # type: ignore

    def __init__(self, *args, **kwargs) -> None:
        """Instantiates a new MousePerspective."""
        Gtk.Overlay.__init__(self, *args, **kwargs)
        self._device: Optional[RatbagdDevice] = None
        self._profile: Optional[RatbagdProfile] = None
        self._notification_error_timeout_id = 0

    @GObject.Property
    def name(self) -> str:
        """The name of this perspective."""
        return "mouse_perspective"

    @GObject.Property
    def titlebar(self) -> Gtk.Widget:
        """The titlebar to this perspective."""
        return self._titlebar

    @GObject.Property
    def can_go_back(self) -> bool:
        """Whether this perspective wants a back button to be displayed in case
        there is more than one connected device."""
        return True

    @GObject.Property
    def can_shutdown(self) -> bool:
        if self._device is None:
            return True

        """Whether this perspective can safely shutdown."""
        return all(not profile.dirty for profile in self._device.profiles)

    @GObject.Property
    def device(self) -> RatbagdDevice:
        assert self._device is not None
        return self._device

    def set_device(self, device: RatbagdDevice) -> None:
        self._device = device

        self._update_device_label(device)

        # The header shows the charge of the device itself, not of a profile.
        self.box_battery.set_no_show_all(True)
        self._update_battery(device)
        connect_signal_with_weak_ref(
            self,
            device,
            "notify::battery-percentage",
            self._on_device_battery_changed,
        )
        connect_signal_with_weak_ref(
            self, device, "resync", lambda _: self._show_notification_error()
        )
        connect_signal_with_weak_ref(
            self,
            self._device,
            "active-profile-changed",
            self._on_active_profile_changed,
        )

        active_profile = device.active_profile
        assert active_profile is not None
        self._set_profile(active_profile)

        self.button_profile.set_visible(len(device.profiles) > 1)

        self.listbox_profiles.foreach(Gtk.Widget.destroy)
        for profile in device.profiles:
            connect_signal_with_weak_ref(
                self, profile, "notify::disabled", self._on_profile_notify_disabled
            )
            connect_signal_with_weak_ref(
                self, profile, "notify::dirty", self._on_profile_notify_dirty
            )
            row = ProfileRow(profile)
            self.listbox_profiles.insert(row, profile.index)

        self._on_profile_notify_disabled(active_profile, None)

        self._select_profile_row(active_profile)

    _BATTERY_ICONS = (
        (90, "battery-full-symbolic"),
        (60, "battery-good-symbolic"),
        (30, "battery-low-symbolic"),
        (0, "battery-caution-symbolic"),
    )

    def _update_device_label(self, device: RatbagdDevice) -> None:
        """Put the make and model in the header, so the main screen says what is
        being configured."""
        name = device.name or ""
        model = device.model or ""
        self.label_device.set_label(name)
        self.label_device.set_tooltip_text(f"{name} ({model})" if model else name)

    def _update_battery(self, device: RatbagdDevice) -> None:
        if not device.has_battery:
            self.box_battery.hide()
            return

        percentage = device.battery_percentage
        status = device.battery_status
        tooltip = {
            RatbagBatteryStatus.DISCHARGING: _("Running on battery"),
            RatbagBatteryStatus.RECHARGING: _("Charging"),
            RatbagBatteryStatus.FULL: _("Fully charged"),
        }.get(status, _("Battery status unknown"))
        self.label_battery.set_label(f"{percentage}%")
        self.label_battery.set_tooltip_text(tooltip)

        icon = next(
            name for threshold, name in self._BATTERY_ICONS if percentage >= threshold
        )
        if status == RatbagBatteryStatus.RECHARGING:
            icon = "battery-level-0-charging-symbolic"
        elif status == RatbagBatteryStatus.FULL:
            icon = "battery-full-charged-symbolic"

        theme = Gtk.IconTheme.get_default()
        if theme is not None and theme.has_icon(icon):
            self.image_battery.set_from_icon_name(icon, Gtk.IconSize.BUTTON)
            self.image_battery.show()
        else:
            self.image_battery.hide()

        self.box_battery.show()

    def _on_device_battery_changed(self, device, _pspec=None) -> None:
        self._update_battery(device)

    def _select_profile_row(self, profile: RatbagdProfile) -> None:
        for row in self.listbox_profiles.get_children():
            if row.profile is profile:
                self.listbox_profiles.select_row(row)
                self.label_profile.set_label(row.name)
                break

    def _set_profile(self, profile: RatbagdProfile) -> None:
        assert self._device is not None

        self._select_profile_row(profile)

        self._profile = profile

        self.stack.foreach(Gtk.Widget.destroy)
        if profile.resolutions:
            self.stack.add_titled(
                ResolutionsPage(self._device, profile), "resolutions", _("Resolutions")
            )
        if profile.buttons:
            self.stack.add_titled(
                ButtonsPage(self._device, profile), "buttons", _("Buttons")
            )
        if profile.leds:
            self.stack.add_titled(LedsPage(self._device, profile), "leds", _("LEDs"))
        # TODO: get rid of this duplicated logic.
        are_report_rates_supported = (
            profile.report_rate != 0 and len(profile.report_rates) != 0
        )
        if (
            profile.angle_snapping != -1
            or profile.debounces
            or are_report_rates_supported
        ):
            self.stack.add_titled(
                AdvancedPage(self._device, profile), "advanced", _("Advanced")
            )

        self._on_profile_notify_dirty(profile, None)

    def _hide_notification_error(self) -> None:
        if self._notification_error_timeout_id != 0:
            GLib.Source.remove(self._notification_error_timeout_id)
            self._notification_error_timeout_id = 0
        self.notification_error.set_reveal_child(False)

    def _show_notification_error(self) -> None:
        self.notification_error.set_reveal_child(True)
        self._notification_error_timeout_id = GLib.timeout_add_seconds(
            5, self._on_notification_error_timeout
        )

    def _on_active_profile_changed(
        self, _device: RatbagdDevice, profile: RatbagdProfile
    ) -> None:
        # TODO: preserve the active tab.
        self._set_profile(profile)

    def _on_notification_error_timeout(self) -> bool:
        self._hide_notification_error()
        return False

    @Gtk.Template.Callback("_on_save_button_clicked")
    def _on_save_button_clicked(self, _button: Gtk.Button) -> None:
        assert self._device is not None
        self._device.commit()

    @Gtk.Template.Callback("_on_notification_error_close_clicked")
    def _on_notification_error_close_clicked(self, button: Gtk.Button) -> None:
        self._hide_notification_error()

    @Gtk.Template.Callback("_on_profile_row_activated")
    def _on_profile_row_activated(self, listbox: Gtk.ListBox, row: ProfileRow) -> None:
        row.set_active()

    @Gtk.Template.Callback("_on_add_profile_button_clicked")
    def _on_add_profile_button_clicked(self, button: Gtk.Button) -> None:
        assert self._device is not None
        # Enable the first disabled profile we find.
        for profile in self._device.profiles:
            if not profile.disabled:
                continue
            profile.disabled = False
            break

    def _on_profile_notify_disabled(
        self, profile: RatbagdProfile, pspec: Optional[GObject.ParamSpec]
    ) -> None:
        assert self._device is not None

        self.add_profile_button.set_sensitive(
            any(p.disabled for p in self._device.profiles)
        )

    def _on_profile_notify_dirty(
        self, profile: RatbagdProfile, pspec: Optional[GObject.ParamSpec]
    ) -> None:
        assert self._device is not None

        device_dirty = any(p.dirty for p in self._device.profiles)

        style_context = self.button_commit.get_style_context()
        if device_dirty:
            style_context.add_class("suggested-action")
            self.button_commit.set_sensitive(True)
        else:
            # There is no way to make a single profile non-dirty, so this works
            # for now. Ideally, this should however check if there are any other
            # profiles on the device that are dirty.
            style_context.remove_class("suggested-action")
            self.button_commit.set_sensitive(False)
