import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gio, Adw  # noqa: E402

from .window import MainWindow  # noqa: E402
from .dialogs import PreferencesWindow, NewProjectDialog, OnboardingWindow  # noqa: E402


class TexManagerApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="org.example.TexManager",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._register_actions()

    def _register_actions(self):
        self.create_action("quit", lambda *_: self.quit())
        self.create_action("preferences", self._on_preferences)
        self.create_action("about", self._on_about)
        self.create_action("new-project", self._on_new_project)
        self.create_action("onboarding", self._on_onboarding)

    def do_activate(self):
        win = self.props.active_window
        if win is None:
            win = MainWindow(application=self)
        win.present()

    # ---- actions ----
    def _on_preferences(self, *_):
        PreferencesWindow(transient_for=self.props.active_window).present()

    def _on_about(self, *_):
        Adw.AboutDialog(
            application_name="TeXManager",
            application_icon="system-software-install-symbolic",
            version="0.1.0",
            developer_name="TeXManager contributors",
            comments="Inspection, installation and lifecycle manager for TeX Live.",
        ).present(self.props.active_window)

    def _on_new_project(self, *_):
        NewProjectDialog(transient_for=self.props.active_window).present()

    def _on_onboarding(self, *_):
        OnboardingWindow(transient_for=self.props.active_window).present()

    # ---- helpers ----
    def create_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        return action
