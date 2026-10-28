# SPDX-License-Identifier: GPL-2.0-or-later

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
    debounce: Gtk.ComboBox = Gtk.Template.Child()  # type: ignore
    report_rate: Gtk.ComboBox = Gtk.Template.Child()  # type: ignore

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
