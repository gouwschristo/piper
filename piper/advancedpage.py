# SPDX-License-Identifier: GPL-2.0-or-later

from gettext import gettext as _
from typing import Optional
import gi

from .mousemap import MouseMap
from .ratbagd import RatbagdDevice, RatbagdProfile
from .util.gobject import connect_signal_with_weak_ref
from .util.valueselector import ValueSelector

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk  # noqa: E402


@Gtk.Template(resource_path="/org/freedesktop/Piper/ui/AdvancedPage.ui")
class AdvancedPage(Gtk.Box):
    """
    Advanced settings stack.
    """

    __gtype_name__ = "AdvancedPage"

    angle_snapping: Gtk.Switch = Gtk.Template.Child()  # type: ignore
    bhop_timeout: ValueSelector = Gtk.Template.Child()  # type: ignore
    debounce: ValueSelector = Gtk.Template.Child()  # type: ignore
    debounce_row: Gtk.Box = Gtk.Template.Child()  # type: ignore
    device_mode: ValueSelector = Gtk.Template.Child()  # type: ignore
    device_mode_note: Gtk.Label = Gtk.Template.Child()  # type: ignore
    device_mode_row: Gtk.Box = Gtk.Template.Child()  # type: ignore
    lod: ValueSelector = Gtk.Template.Child()  # type: ignore
    lod_note: Gtk.Label = Gtk.Template.Child()  # type: ignore
    power_off_timeout: ValueSelector = Gtk.Template.Child()  # type: ignore
    power_save_timeout: ValueSelector = Gtk.Template.Child()  # type: ignore
    report_rate: ValueSelector = Gtk.Template.Child()  # type: ignore
    shift_resolution: ValueSelector = Gtk.Template.Child()  # type: ignore

    def __init__(
        self, device: RatbagdDevice, profile: RatbagdProfile, *args, **kwargs
    ) -> None:
        """Instantiates a new AdvancedPage."""
        Gtk.Box.__init__(self, *args, **kwargs)

        self._profile = profile
        self._combo_entries = {}

        self.debounce.set_entries([(ms, str(ms)) for ms in profile.debounces])
        self.debounce_row.set_no_show_all(True)
        if not profile.debounces:
            # The device does not do debounce at all: an empty selector is
            # worse than no selector, so hide the row.
            self.debounce_row.hide()
        else:
            self._show_subtree(self.debounce_row)

        self._handler_debounce = self.debounce.connect(
            "changed", self._on_debounce_combo_changed
        )

        self._profile_debounce_time_changed_handler = connect_signal_with_weak_ref(
            self,
            self._profile,
            "notify::debounce",
            self._on_profile_debounce_time_changed,
        )
        self._update_widget_debounce_time()

        # The rate list comes from the device, which may offer more than the
        # four classic 125/250/500/1000 Hz steps (e.g. 2000/4000/8000 Hz on
        # LIGHTSPEED mice). Listing them dynamically keeps every rate the
        # profile reports selectable.
        self._rates = list(profile.report_rates)
        self.report_rate.set_entries([(hz, str(hz)) for hz in self._rates])

        self.report_rate.set_sensitive(
            profile.report_rate != 0 and len(self._rates) != 0
        )

        self._handler_report_rate = self.report_rate.connect(
            "changed", self._on_report_rate_changed
        )

        self._profile_report_rate_changed_handler = connect_signal_with_weak_ref(
            self,
            self._profile,
            "notify::report-rate",
            self._on_profile_report_rate_changed,
        )
        self._update_widget_report_rate()

        profile = self._profile

        self._mousemap = MouseMap("#Buttons", device, spacing=20, border_width=20)
        self.pack_start(self._mousemap, True, True, 0)

        self._setup_bhop_timeout(profile)
        self._setup_power_save_timeout(profile)
        self._setup_power_off_timeout(profile)
        self._setup_shift_resolution(profile)
        self._setup_lod(profile)
        self._setup_device_mode(device)

        self._angle_snapping_switch_handler = self.angle_snapping.connect(
            "state-set", self._on_angle_snapping_switch_state_set
        )

        self.angle_snapping.set_sensitive(profile.angle_snapping != -1)

        self._profile_angle_snapping_changed_handler = connect_signal_with_weak_ref(
            self,
            self._profile,
            "notify::angle-snapping",
            self._on_profile_angle_snapping_changed,
        )
        self._update_widget_angle_snapping()

        self.show_all()

    def _on_profile_debounce_time_changed(
        self, profile: RatbagdProfile, pspec: Optional[GObject.ParamSpec]
    ) -> None:
        self._update_widget_debounce_time()

    def _update_widget_debounce_time(self) -> None:
        profile = self._profile

        with self.debounce.handler_block(self._handler_debounce):
            if profile.debounce in profile.debounces:
                self.debounce.set_active_id(str(profile.debounce))
            elif profile.debounces:
                self.debounce.set_active_id(str(profile.debounces[0]))
            else:
                self.debounce.set_active_id("")

    def _on_debounce_combo_changed(self, combo: ValueSelector) -> None:
        value = self._combo_value(combo)
        if value is None or value not in self._profile.debounces:
            return
        profile = self._profile
        with profile.handler_block(self._profile_debounce_time_changed_handler):
            profile.debounce = value

    def _on_angle_snapping_switch_state_set(
        self, button: Gtk.Switch, state: bool
    ) -> None:
        profile = self._profile
        with profile.handler_block(self._profile_angle_snapping_changed_handler):
            profile.angle_snapping = 1 if state else 0

    def _on_profile_angle_snapping_changed(
        self, profile: RatbagdProfile, pspec: Optional[GObject.ParamSpec]
    ) -> None:
        self._update_widget_angle_snapping()

    def _update_widget_angle_snapping(self) -> None:
        with self.angle_snapping.handler_block(self._angle_snapping_switch_handler):
            self.angle_snapping.set_active(self._profile.angle_snapping == 1)

    def _make_combo(self, combo: ValueSelector, entries) -> None:
        """Fill a combo with (value, label) pairs and select the current one.

        GtkComboBoxText rather than GtkComboBox: with a hand-built cell
        renderer GTK measures the popup before the rows are sized, so the menu
        opens collapsed until it is scrolled. The list is kept here because
        GtkComboBoxText does not expose its model.
        """
        combo.set_entries(list(entries))
        self._combo_entries[combo] = list(entries)

    def _combo_select(self, combo: ValueSelector, handler, value) -> None:
        with combo.handler_block(handler):
            combo.set_active_id(str(value))

    def _combo_value(self, combo: ValueSelector):
        active = combo.get_active_id()
        return None if active is None else int(active)

    def _setup_value_combo(
        self, combo, handler_attr, values, current, signal, setter, supported
    ) -> None:
        """Shared setup for a combo that maps directly onto a profile value."""
        if not supported:
            combo.set_sensitive(False)
            return
        self._make_combo(combo, values)
        handler = combo.connect("changed", self._on_value_combo_changed, setter)
        setattr(self, handler_attr, handler)
        self._combo_select(combo, handler, current)
        connect_signal_with_weak_ref(
            self, self._profile, f"notify::{signal}", self._on_profile_value_changed,
            combo, handler_attr, signal, setter,
        )

    def _on_value_combo_changed(self, combo: ValueSelector, setter) -> None:
        value = self._combo_value(combo)
        if value is None:
            return
        setattr(self._profile, setter, value)

    def _on_profile_value_changed(
        self, profile, pspec, combo, handler_attr, signal, setter
    ) -> None:
        self._combo_select(combo, getattr(self, handler_attr), getattr(profile, setter))

    def _setup_bhop_timeout(self, profile) -> None:
        # The device stores 0 (off) or 100..1000 ms in 100 ms steps, which is
        # what G HUB offers.
        values = [(0, _("Off"))] + [(ms, f"{ms} ms") for ms in range(100, 1001, 100)]
        self._setup_value_combo(
            self.bhop_timeout, "_bhop_handler", values, profile.bhop_timeout,
            "bhop-timeout", "bhop_timeout", profile.bhop_timeout != -1,
        )

    def _setup_power_save_timeout(self, profile) -> None:
        values = [(s, f"{s} s") for s in (30, 60, 120, 300, 600)]
        if profile.power_save_timeout not in (v for v, _ in values):
            values.append((profile.power_save_timeout, f"{profile.power_save_timeout} s"))
            values.sort()
        self._setup_value_combo(
            self.power_save_timeout, "_power_save_handler", values,
            profile.power_save_timeout, "power-save-timeout", "power_save_timeout",
            profile.power_save_timeout != -1,
        )

    def _setup_power_off_timeout(self, profile) -> None:
        values = [(s, f"{s} s") for s in (120, 300, 600, 1200, 1800)]
        if profile.power_off_timeout not in (v for v, _ in values):
            values.append((profile.power_off_timeout, f"{profile.power_off_timeout} s"))
            values.sort()
        self._setup_value_combo(
            self.power_off_timeout, "_power_off_handler", values,
            profile.power_off_timeout, "power-off-timeout", "power_off_timeout",
            profile.power_off_timeout != -1,
        )

    def _active_resolution(self, profile):
        """The stage the device is currently using, for profile-level display.

        Lift-off distance is stored per DPI stage, so a profile-level control can
        only ever show one of them -- the active one.
        """
        resolutions = list(profile.resolutions)
        for res in resolutions:
            if res.is_active:
                return res
        for res in resolutions:
            if res.is_default:
                return res
        return resolutions[0] if resolutions else None

    def _setup_lod(self, profile) -> None:
        from .ratbagd import RatbagdResolution

        res = self._active_resolution(profile)
        self._lod_resolution = res

        if res is None or RatbagdResolution.CAP_LOD not in res.capabilities:
            self.lod.set_sensitive(False)
            # show_all() runs at the end of __init__, so plain set_visible(False)
            # would be undone; opt the note out of it first.
            self.lod_note.set_no_show_all(True)
            self.lod_note.hide()
            return

        values = [
            (RatbagdResolution.LOD_LOW, _("Low")),
            (RatbagdResolution.LOD_MEDIUM, _("Medium")),
            (RatbagdResolution.LOD_HIGH, _("High")),
        ]
        self._lod_values = [v for v, _ in values]
        self._make_combo(self.lod, values)
        self._lod_handler = self.lod.connect("changed", self._on_lod_changed)
        self._combo_select(self.lod, self._lod_handler, res.lod)
        connect_signal_with_weak_ref(
            self, res, "notify::lod", self._on_resolution_lod_changed
        )

    def _on_lod_changed(self, combo: ValueSelector) -> None:
        value = self._combo_value(combo)
        if value is None or self._lod_resolution is None:
            return
        self._lod_resolution.lod = value

    def _on_resolution_lod_changed(self, res, _pspec=None) -> None:
        if self._lod_resolution is res:
            self._combo_select(self.lod, self._lod_handler, res.lod)

    @staticmethod
    def _show_subtree(widget: Gtk.Widget) -> None:
        """Show a widget and its children even if it has no_show_all set.

        gtk_widget_show_all() does nothing at all on a widget that carries
        no_show_all, so the flag has to come off for the call and go back on
        afterwards; otherwise a later window-wide show_all() would re-show a row
        we deliberately hid.
        """
        widget.set_no_show_all(False)
        widget.show_all()
        widget.set_no_show_all(True)

    def _setup_device_mode(self, device: RatbagdDevice) -> None:
        # Device mode is a device-wide toggle, not a profile value: the mouse
        # either applies the profiles stored in its own flash or lets the host
        # drive it. Devices without the switch do not show the row at all.
        for widget in (self.device_mode_row, self.device_mode_note):
            widget.set_no_show_all(True)

        if device is None or not device.has_onboard_mode_capability:
            self.device_mode_row.hide()
            self.device_mode_note.hide()
            return

        # set_no_show_all() above stops show_all() from descending into the row,
        # so the subtree has to be shown explicitly or its label never appears.
        self._show_subtree(self.device_mode_row)
        self._show_subtree(self.device_mode_note)

        self._device = device
        self._make_combo(
            self.device_mode,
            [
                (1, _("On-board profiles")),
                (0, _("Host (software) control")),
            ],
        )
        self._device_mode_handler = self.device_mode.connect(
            "changed", self._on_device_mode_changed
        )
        self._combo_select(
            self.device_mode,
            self._device_mode_handler,
            1 if device.onboard_mode else 0,
        )
        connect_signal_with_weak_ref(
            self,
            device,
            "notify::onboard-mode",
            self._on_device_onboard_mode_changed,
        )

    def _on_device_mode_changed(self, combo: ValueSelector) -> None:
        value = self._combo_value(combo)
        if value is None or self._device is None:
            return
        if bool(value) != self._device.onboard_mode:
            self._device.onboard_mode = bool(value)

    def _on_device_onboard_mode_changed(self, device, _pspec=None) -> None:
        self._combo_select(
            self.device_mode,
            self._device_mode_handler,
            1 if device.onboard_mode else 0,
        )

    def _setup_shift_resolution(self, profile) -> None:
        values = [(r.index, f"{r.index}: {r.resolution[0]} dpi") for r in profile.resolutions]
        self._setup_value_combo(
            self.shift_resolution, "_shift_handler", values, profile.shift_resolution,
            "shift-resolution", "shift_resolution", profile.shift_resolution != -1,
        )

    def _on_report_rate_changed(self, combo: ValueSelector) -> None:
        value = self._combo_value(combo)
        if value is None or value not in self._rates:
            return
        profile = self._profile
        with profile.handler_block(self._profile_report_rate_changed_handler):
            profile.report_rate = value

    def _on_profile_report_rate_changed(
        self, profile: RatbagdProfile, pspec: Optional[GObject.ParamSpec]
    ) -> None:
        self._update_widget_report_rate()

    def _update_widget_report_rate(self) -> None:
        rate = self._profile.report_rate

        with self.report_rate.handler_block(self._handler_report_rate):
            if rate in self._rates:
                self.report_rate.set_active_id(str(rate))
            else:
                # A rate the device no longer advertises: show nothing rather
                # than silently claiming a different rate is selected.
                self.report_rate.set_active_id("")
