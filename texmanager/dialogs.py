import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GObject, GLib, Gio, Gtk, Adw  # noqa: E402

import threading

from . import backend  # noqa: E402
from .models import TemplateItem  # noqa: E402


TEMPLATE_CARD_FACTORY = b"""
<interface>
  <template class="GtkListItem">
    <object class="GtkButton">
      <property name="hexpand">1</property>
      <property name="vexpand">1</property>
      <style>
        <class name="card"/>
      </style>
      <child>
        <object class="GtkBox">
          <property name="orientation">vertical</property>
          <property name="spacing">6</property>
          <property name="margin">12</property>
          <child>
            <object class="GtkImage">
              <property name="icon-name">document-new-symbolic</property>
              <property name="pixel-size">32</property>
            </object>
          </child>
          <child>
            <object class="GtkLabel">
              <property name="xalign">0</property>
              <binding name="label">
                <lookup name="name" type="TemplateItem">
                  <lookup name="item">GtkListItem</lookup>
                </lookup>
              </binding>
            </object>
          </child>
          <child>
            <object class="GtkLabel">
              <property name="xalign">0</property>
              <property name="wrap">1</property>
              <property name="css-classes">dim-label</property>
              <binding name="label">
                <lookup name="description" type="TemplateItem">
                  <lookup name="item">GtkListItem</lookup>
                </lookup>
              </binding>
            </object>
          </child>
        </object>
      </child>
    </object>
  </template>
</interface>
"""


def _list_factory(xml: bytes) -> Gtk.BuilderListItemFactory:
    return Gtk.BuilderListItemFactory(bytes=GLib.Bytes(xml))


class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(520, 560)
        self.set_title("Preferences")

        update_page = Adw.PreferencesPage(title="Updates",
                                         icon_name="software-update-symbolic")
        update_group = Adw.PreferencesGroup(title="Automatic Updates")
        self.auto_update = Adw.SwitchRow(
            title="Check for updates automatically",
            subtitle="Runs a lightweight check in the background")
        self.auto_update.connect("notify::active", self.on_auto_update_toggled)
        update_group.add(self.auto_update)

        self.update_interval = Adw.ComboRow(
            title="Interval",
            model=Gtk.StringList.new(["Daily", "Weekly", "Monthly"]))
        self.update_interval.connect("notify::selected", self.on_interval_changed)
        update_group.add(self.update_interval)
        update_page.add(update_group)
        self.add(update_page)

        general_page = Adw.PreferencesPage(title="General",
                                           icon_name="preferences-system-symbolic")
        general_group = Adw.PreferencesGroup(title="Behavior")
        confirm = Adw.SwitchRow(title="Confirm destructive actions",
                               subtitle="Show a confirmation before deleting "
                                        "or overwriting",
                               active=True)
        general_group.add(confirm)

        appearance_group = Adw.PreferencesGroup(title="Appearance")
        self.theme_selector = Adw.ComboRow(
            title="Theme",
            subtitle="Follow system preference",
            model=Gtk.StringList.new(["System", "Light", "Dark"]))
        self.theme_selector.connect("notify::selected", self.on_theme_changed)
        appearance_group.add(self.theme_selector)
        general_group.add(appearance_group)
        general_page.add(general_group)
        self.add(general_page)

    def on_auto_update_toggled(self, *args):  # C.2
        self.update_interval.set_sensitive(self.auto_update.get_active())

    def on_interval_changed(self, *args):  # C.2
        pass

    def on_theme_changed(self, *args):
        selected = self.theme_selector.get_selected()
        if selected is None or selected < 0:
            return
        model = self.theme_selector.get_model()
        theme = model.get_string(selected)
        style = Adw.StyleManager.get_default()
        if theme == "Light":
            style.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif theme == "Dark":
            style.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            style.set_color_scheme(Adw.ColorScheme.DEFAULT)


class NewProjectDialog(Adw.Dialog):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("New Project")
        self.set_content_width(560)
        self.set_content_height(480)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        create = Gtk.Button(label="Create", css_classes=["suggested-action"])
        create.connect("clicked", self.on_create)
        header.pack_end(create)
        toolbar.add_top_bar(header)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_top=12, margin_bottom=12,
                       margin_start=12, margin_end=12)
        vbox.append(Gtk.Label(label="Choose a template", xalign=0))

        self.template_grid = Gtk.GridView(
            factory=_list_factory(TEMPLATE_CARD_FACTORY),
            max_columns=2, min_columns=2, vexpand=True)
        store = Gio.ListStore.new(TemplateItem)
        store.append(TemplateItem("Article", "Standard article with sections."))
        store.append(TemplateItem("Beamer", "Presentation slides."))
        store.append(TemplateItem("Thesis / Report", "Long-form book/report."))
        store.append(TemplateItem("CV / Resume", "Single-page curriculum vitae."))
        self.template_grid.set_model(Gtk.NoSelection(model=store))
        vbox.append(self.template_grid)

        folder_row = Adw.ActionRow(title="Location",
                                  subtitle="No folder selected")
        folder_btn = Gtk.Button(label="Choose…")
        folder_btn.connect("clicked", self.on_choose_folder)
        folder_row.add_suffix(folder_btn)
        vbox.append(folder_row)

        toolbar.set_content(vbox)
        self.set_child(toolbar)

    def on_create(self, *args):  # E.1
        self.close()

    def on_choose_folder(self, *args):  # E.1
        pass


class DependencyCheckDialog(Adw.AlertDialog):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_heading("Dependency Check")
        self.set_body("Packages required by the active .tex file.")
        self.set_default_response("close")
        self.add_response("close", "Close")

        clamp = Adw.Clamp(maximum_size=480)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        dep_list = Gtk.ListBox(css_classes=["boxed-list"])
        installed = Adw.ActionRow(title="graphicx")
        installed.add_suffix(Gtk.Label(label="✓ Installed",
                                       css_classes=["success"]))
        missing = Adw.ActionRow(title="tikz")
        missing.add_suffix(Gtk.Label(label="⚠ Missing", css_classes=["warning"]))
        dep_list.append(installed)
        dep_list.append(missing)
        vbox.append(dep_list)
        install = Gtk.Button(label="Install 1 Missing Package",
                             css_classes=["suggested-action"])
        install.connect("clicked", self.on_install_missing)
        vbox.append(install)
        clamp.set_child(vbox)
        self.set_extra_child(clamp)

    def on_install_missing(self, *args):  # A.2
        self.close()


class OnboardingWindow(Adw.Window):
    def __init__(self, year=None, **kwargs):
        super().__init__(**kwargs)
        self._year = year
        self._current_page = 0
        self.set_default_size(560, 620)
        self.set_title(f"Install TeX Live {year}" if year else "Set up TeXManager")
        self.set_modal(True)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        skip = Gtk.Button(label="Skip")
        skip.connect("clicked", self.on_skip)
        header.pack_end(skip)
        toolbar.add_top_bar(header)

        clamp = Adw.Clamp(maximum_size=480, margin_top=16, margin_bottom=16,
                          margin_start=16, margin_end=16)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        carousel = Adw.Carousel(hexpand=True, vexpand=True)
        carousel.set_property("allow-mouse-drag", False)
        carousel.set_property("allow-scroll-wheel", False)
        welcome = Adw.StatusPage(icon_name="system-software-install-symbolic",
                                 title="Welcome",
                                 description="Install and manage TeX Live on "
                                             "this machine.",
                                 hexpand=True, vexpand=True)
        carousel.append(welcome)

        scheme_page = Adw.PreferencesPage(hexpand=True, vexpand=True)
        scheme_group = Adw.PreferencesGroup(title="Installation Scheme")
        self.scheme_picker = Adw.ComboRow(
            title="Scheme", subtitle="scheme-medium — approx. 1.8 GB",
            model=Gtk.StringList.new([
                "scheme-infraonly", "scheme-basic", "scheme-minimal",
                "scheme-small", "scheme-medium", "scheme-full"]))
        self.scheme_picker.connect("notify::selected", self.on_scheme_changed)
        scheme_group.add(self.scheme_picker)
        self.scheme_desc = Gtk.Label(
            label="",
            wrap=True,
            xalign=0,
            css_classes=["dim-label"],
            margin_top=6,
            margin_bottom=6)
        scheme_group.add(self.scheme_desc)
        mirror_group = Adw.PreferencesGroup(title="Download Mirror")
        self.mirror_picker = Adw.ComboRow(title="Mirror",
                                          subtitle="Auto (nearest)",
                                          model=Gtk.StringList.new(
                                              ["Auto (nearest)"]))
        refresh = Gtk.Button(icon_name="view-refresh-symbolic",
                             tooltip_text="Re-run latency probe")
        refresh.connect("clicked", self.on_refresh_mirror)
        self.mirror_picker.add_suffix(refresh)
        mirror_group.add(self.mirror_picker)
        scheme_page.add(scheme_group)
        scheme_page.add(mirror_group)
        carousel.append(scheme_page)

        progress_page = Adw.PreferencesPage(hexpand=True, vexpand=True)
        progress_group = Adw.PreferencesGroup(title="Install")
        self.install_progress = Gtk.ProgressBar(fraction=0.0, show_text=True,
                                                text="Idle")
        self.retry_status = Gtk.Label(label="", css_classes=["dim-label"],
                                      visible=False)
        progress_group.add(self.install_progress)
        progress_group.add(self.retry_status)
        progress_page.add(progress_group)
        carousel.append(progress_page)

        self._carousel = carousel
        self._pages = [welcome, scheme_page, progress_page]
        vbox.append(carousel)

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                      halign=Gtk.Align.END)
        self._back_btn = Gtk.Button(label="Back")
        self._back_btn.connect("clicked", self.on_back)
        self._next_btn = Gtk.Button(label="Next", css_classes=["suggested-action"])
        self._next_btn.connect("clicked", self.on_next)
        nav.append(self._back_btn)
        nav.append(self._next_btn)
        vbox.append(nav)

        clamp.set_child(vbox)
        toolbar.set_content(clamp)
        self.set_content(toolbar)

    def on_skip(self, *args):  # B.*
        self.close()

    def on_scheme_changed(self, *args):  # B.1
        selected = self.scheme_picker.get_selected()
        if selected is None or selected < 0:
            return
        model = self.scheme_picker.get_model()
        scheme = model.get_string(selected)
        sizes = {
            "scheme-infraonly": "approx. 0.2 GB",
            "scheme-basic": "approx. 0.5 GB",
            "scheme-minimal": "approx. 0.7 GB",
            "scheme-small": "approx. 1.0 GB",
            "scheme-medium": "approx. 1.8 GB",
            "scheme-full": "approx. 4.4 GB",
        }
        descs = {
            "scheme-infraonly": "Essential infrastructure only — no extra packages or documentation.",
            "scheme-basic": "Basic TeX and LaTeX with a small set of common packages.",
            "scheme-minimal": "Minimal TeX/LaTeX setup, no additional packages.",
            "scheme-small": "Small curated set of commonly used packages.",
            "scheme-medium": "Medium package set suitable for typical documents.",
            "scheme-full": "Complete TeX Live installation with all available packages.",
        }
        self.scheme_picker.set_subtitle(f"{scheme} — {sizes.get(scheme, 'unknown size')}")
        self.scheme_desc.set_label(descs.get(scheme, ""))

    def on_refresh_mirror(self, *args):  # B.2
        self.mirror_picker.set_subtitle("Auto (nearest)")

    def on_back(self, *args):  # B.*
        if self._current_page > 0:
            self._current_page -= 1
            self._carousel.scroll_to(self._pages[self._current_page], True)

    def on_next(self, *args):  # B.3
        if self._current_page == 0:
            self._current_page += 1
            self._carousel.scroll_to(self._pages[self._current_page], True)
        elif self._current_page == 1:
            self._start_install()
        elif self._current_page == 2:
            self.close()

    def _start_install(self):
        self._current_page += 1
        self._carousel.scroll_to(self._pages[self._current_page], True)

        self._back_btn.set_sensitive(False)
        self._next_btn.set_sensitive(False)
        self._next_btn.set_label("Installing…")

        scheme_model = self.scheme_picker.get_model()
        selected = self.scheme_picker.get_selected()
        scheme = scheme_model.get_string(selected)

        def worker():
            try:
                def progress(line):
                    GLib.idle_add(self._on_install_progress, line)
                backend.install_texlive(self._year, scheme, progress_callback=progress)
                GLib.idle_add(self._on_install_complete, None)
            except Exception as exc:
                GLib.idle_add(self._on_install_complete, str(exc))

        self._install_thread = threading.Thread(target=worker, daemon=True)
        self._install_thread.start()
        self.install_progress.set_fraction(0.0)
        self.install_progress.set_text("Starting…")
        self.retry_status.set_visible(False)

    def _on_install_progress(self, line):
        self.install_progress.set_text(line[:120])

    def _on_install_complete(self, error):
        self._back_btn.set_sensitive(True)
        self._next_btn.set_sensitive(True)
        if error:
            self.install_progress.set_fraction(0.0)
            self.install_progress.set_text("Failed")
            self.retry_status.set_label(error[:300])
            self.retry_status.set_visible(True)
            self._next_btn.set_label("Close")
        else:
            self.install_progress.set_fraction(1.0)
            self.install_progress.set_text("Installation complete")
            self._next_btn.set_label("Close")


def show_confirm(parent, title, summary, details, on_confirm):
    """Shared destructive-action confirmation dialog (X.2)."""
    dialog = Adw.AlertDialog(heading=title, body=summary)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("confirm", "Confirm")
    dialog.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_default_response("cancel")
    dialog.set_close_response("cancel")

    if details:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for item in details:
            box.append(Gtk.Label(label=item, xalign=0))
        dialog.set_extra_child(box)

    def _response(d, r):
        if r == "confirm":
            on_confirm()

    dialog.connect("response", _response)
    dialog.present(parent)
