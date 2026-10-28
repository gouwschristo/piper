# SPDX-License-Identifier: GPL-2.0-or-later

from gettext import gettext as _
from typing import Optional
import gi

from .mousemap import MouseMap
from .ratbagd import RatbagdDevice, RatbagdProfile
from .util.gobject import connect_signal_with_weak_ref

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk  # noqa: E402


@Gtk.Template(resource_path="/org/freedesktop/Piper/ui/AdvancedPage.ui")
class AdvancedPage(Gtk.Box):
    """
    Advanced settings stack.
    """

    __gtype_name__ = "AdvancedPage"

    angle_snapping: Gtk.Switch = Gtk.Template.Child()  # type: ignore
    bhop_timeout: Gtk.ComboBox = Gtk.Template.Child()  # type: ignore
    debounce: Gtk.ComboBox = Gtk.Template.Child()  # type: ignore
    power_off_timeout: Gtk.ComboBox = Gtk.Template.Child()  # type: ignore
    power_save_timeout: Gtk.ComboBox = Gtk.Template.Child()  # type: ignore
    report_rate: Gtk.ComboBox = Gtk.Template.Child()  # type: ignore
    shift_resolution: Gtk.ComboBox = Gtk.Template.Child()  # type: ignore

    def __init__(
        self, device: RatbagdDevice, profile: RatbagdProfile, *args, **kwargs
    ) -> None:
        """Instantiates a new AdvancedPage."""
        Gtk.Box.__init__(self, *args, **kwargs)

        self._profile = profile

        cell = Gtk.CellRendererText()
        self.debounce.pack_start(cell, True)
        self.debounce.add_attribute(cell, "text", 0)

        model = Gtk.ListStore(str)
        for ms in profile.debounces:
            model.append([str(ms)])
        self.debounce.set_model(model)

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
        cell = Gtk.CellRendererText()
        self.report_rate.pack_start(cell, True)
        self.report_rate.add_attribute(cell, "text", 0)

        model = Gtk.ListStore(str)
        for hz in self._rates:
            model.append([str(hz)])
        self.report_rate.set_model(model)

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
                idx = profile.debounces.index(profile.debounce)
                self.debounce.set_active(idx)
            else:
                self.debounce.set_active(0)

    def _on_debounce_combo_changed(self, combo: Gtk.ComboBox) -> None:
        idx = combo.get_active()
        profile = self._profile
        with profile.handler_block(self._profile_debounce_time_changed_handler):
            profile.debounce = profile.debounces[idx]

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

    def _make_combo(self, combo: Gtk.ComboBox, entries) -> None:
        """Fill a combo with (value, label) pairs and select the current one."""
        cell = Gtk.CellRendererText()
        combo.pack_start(cell, True)
        combo.add_attribute(cell, "text", 1)

        model = Gtk.ListStore(int, str)
        for value, label in entries:
            model.append([value, label])
        combo.set_model(model)

    def _combo_select(self, combo: Gtk.ComboBox, handler, value) -> None:
        model = combo.get_model()
        with combo.handler_block(handler):
            for i, row in enumerate(model):
                if row[0] == value:
                    combo.set_active(i)
                    return
            combo.set_active(-1)

    def _combo_value(self, combo: Gtk.ComboBox):
        idx = combo.get_active()
        if idx < 0:
            return None
        return combo.get_model()[idx][0]

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

    def _on_value_combo_changed(self, combo: Gtk.ComboBox, setter) -> None:
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

    def _setup_shift_resolution(self, profile) -> None:
        values = [(r.index, f"{r.index}: {r.resolution[0]} dpi") for r in profile.resolutions]
        self._setup_value_combo(
            self.shift_resolution, "_shift_handler", values, profile.shift_resolution,
            "shift-resolution", "shift_resolution", profile.shift_resolution != -1,
        )

    def _on_report_rate_changed(self, combo: Gtk.ComboBox) -> None:
        idx = combo.get_active()
        if idx < 0 or idx >= len(self._rates):
            return
        profile = self._profile
        with profile.handler_block(self._profile_report_rate_changed_handler):
            profile.report_rate = self._rates[idx]

    def _on_profile_report_rate_changed(
        self, profile: RatbagdProfile, pspec: Optional[GObject.ParamSpec]
    ) -> None:
        self._update_widget_report_rate()

    def _update_widget_report_rate(self) -> None:
        rate = self._profile.report_rate

        with self.report_rate.handler_block(self._handler_report_rate):
            if rate in self._rates:
                self.report_rate.set_active(self._rates.index(rate))
            else:
                # A rate the device no longer advertises: show nothing rather
                # than silently claiming a different rate is selected.
                self.report_rate.set_active(-1)
