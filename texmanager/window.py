import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import os
import shutil
import subprocess
import threading
from pathlib import Path

from gi.repository import GObject, GLib, Gio, Gtk, Adw, Pango, Gdk  # noqa: E402

from . import backend  # noqa: E402
from .detection import TexInstallation, detect  # noqa: E402
from .dialogs import show_confirm, OnboardingWindow  # noqa: E402
from .history import log_event  # noqa: E402
from .models import PackageItem, TemplateItem  # noqa: E402

_SAFE_TUG_PREFIXES = ("/usr/local/texlive", "/opt/texlive",
                     str(Path.home() / "texlive"))


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


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("TeXManager")
        self.set_default_size(1000, 720)

        self._apply_styles()

        self._primary: TexInstallation | None = None
        self._installations: list[TexInstallation] = []
        self._conflict_radios: list = []
        self._selected_package: str | None = None
        self._updates_loaded: bool = False

        self._build_ui()
        self._populate_packages()
        self._populate_shortcuts()
        self._refresh_installation_status()
        self._select_package_drawer_row("Installed")

    def _apply_styles(self):
        css = """
        .package-row {
            padding: 8px 6px;
            border-radius: 10px;
        }
        .package-row:hover {
            background-color: rgba(127, 127, 127, 0.12);
        }
        .package-name {
            font-weight: 600;
        }
        .package-sub {
            font-size: 0.85em;
        }
        .tab-bar {
            padding: 4px 8px;
            spacing: 4px;
        }
        .tab-bar > togglebutton,
        .tab-bar > button {
            padding: 6px 16px;
            border-radius: 8px 8px 0px 0px;
            margin-bottom: -1px;
            font-weight: 500;
        }
        .tab-bar > togglebutton:checked,
        .tab-bar > button:checked {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _build_ui(self):
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_lbl = Gtk.Label(label="TeXManager")
        title_lbl.add_css_class("title")
        subtitle_lbl = Gtk.Label(label="TeX Live Manager")
        subtitle_lbl.add_css_class("subtitle")
        subtitle_lbl.add_css_class("dim-label")
        title_box.append(title_lbl)
        title_box.append(subtitle_lbl)
        header.set_title_widget(title_box)

        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("Keyboard Shortcuts", "win.show-help-overlay")
        menu.append("About TeXManager", "app.about")
        menu.append("Quit", "app.quit")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic",
                                  tooltip_text="Menu",
                                  popover=Gtk.PopoverMenu(menu_model=menu))
        header.pack_end(menu_btn)
        toolbar.add_top_bar(header)

        stack = Adw.ViewStack(vexpand=True)

        tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tab_bar.add_css_class("tab-bar")
        tab_buttons: list[Gtk.ToggleButton] = []
        tab_map: dict[str, Gtk.ToggleButton] = {}

        def on_tab_clicked(btn, name):
            stack.set_visible_child_name(name)

        def on_stack_page_changed(s, p):
            vcn = stack.get_visible_child_name()
            for name, btn in tab_map.items():
                btn.set_active(name == vcn)

        def add_tab(name, label, icon):
            btn = Gtk.ToggleButton(label=label)
            btn.set_icon_name(icon)
            btn.add_css_class("tab-button")
            btn.connect("clicked", on_tab_clicked, name)
            tab_bar.append(btn)
            tab_buttons.append(btn)
            tab_map[name] = btn

        stack.connect("notify::visible-child", on_stack_page_changed)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(tab_bar)
        content_box.append(stack)
        toolbar.set_content(content_box)

        self._build_overview(stack)
        self._build_packages(stack)
        self._build_compile_watch(stack)
        self._build_utilities(stack)
        for name, label, icon in [
            ("overview", "Overview", "go-home-symbolic"),
            ("packages", "Packages", "system-software-install-symbolic"),
            ("compile", "Compile & Watch", "media-playback-start-symbolic"),
            ("utilities", "Utilities", "preferences-system-symbolic"),
        ]:
            add_tab(name, label, icon)

        # select the first tab
        if tab_buttons:
            tab_buttons[0].set_active(True)

        self.set_content(toolbar)

    # ---- Tab 1: Overview (A.1, A.3, C.1) ----
    def _build_overview(self, stack):
        page = Adw.StatusPage(title="TeXManager",
                              description="Inspection, installation and "
                                          "lifecycle for TeX Live.")
        clamp = Adw.Clamp(maximum_size=700)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)

        self.conflict_banner = Adw.Banner(title="Conflict Detected",
                                          revealed=False,
                                          button_label="Resolve")
        self.conflict_banner.connect("button-clicked", self.on_resolve_conflict)
        vbox.append(self.conflict_banner)

        status_group = Adw.PreferencesGroup(title="Status")
        self.status_row = Adw.ActionRow(title="TeX Installation",
                                        subtitle="No installation detected")
        self.status_icon = Gtk.Image(icon_name="dialog-warning-symbolic",
                                     css_classes=["warning"])
        self.status_row.add_suffix(self.status_icon)
        self.details_btn = Gtk.Button(label="Details",
                                      tooltip_text="Show installation details")
        self.details_btn.connect("clicked", self.on_show_details)
        self.status_row.add_suffix(self.details_btn)
        status_group.add(self.status_row)
        vbox.append(status_group)

        history = Adw.ExpanderRow(title="History",
                                  subtitle="Snapshots for rollback")
        history.set_expanded(False)
        history.add_row(Adw.ActionRow(title="No snapshots yet",
                                      subtitle="Snapshots are recorded before "
                                               "updates"))
        vbox.append(history)

        logs = Adw.ExpanderRow(title="Terminal Execution Logs", expanded=False)
        scroll = Gtk.ScrolledWindow(min_content_height=160)
        text = Gtk.TextView(editable=False, monospace=True,
                            css_classes=["terminal"])
        scroll.set_child(text)
        logs.add_row(scroll)
        vbox.append(logs)

        report_group = Adw.PreferencesGroup(title="Compile Report")
        self.report_chip = Gtk.Button(label="0 errors, 0 warnings",
                                     css_classes=["pill", "suggested-action"])
        self.report_chip.connect("clicked", self.on_expand_report)
        report_group.set_header_suffix(self.report_chip)
        errors = Adw.ExpanderRow(title="Errors", expanded=True)
        errors.add_row(Adw.ActionRow(title="No errors"))
        warnings = Adw.ExpanderRow(title="Warnings", expanded=False)
        warnings.add_row(Adw.ActionRow(title="No warnings"))
        boxes = Adw.ExpanderRow(title="Overfull / Underfull boxes", expanded=False)
        boxes.add_row(Adw.ActionRow(title="No box warnings"))
        report_group.add(errors)
        report_group.add(warnings)
        report_group.add(boxes)
        vbox.append(report_group)

        clamp.set_child(vbox)
        page.set_child(clamp)
        stack.add_titled(page, "overview", "Overview").set_icon_name(
            "go-home-symbolic")

    # ---- Tab 2: Packages (D.1, D.2) ----
    def _build_packages(self, stack):
        split = Adw.NavigationSplitView()

        # sidebar: drawer with Installed / Updates / Categories
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_title_widget(Gtk.Label(label="Packages",
                                                  css_classes=["heading"]))
        sidebar_box.append(sidebar_header)

        drawer = Gtk.ListBox(css_classes=["boxed-list"],
                             selection_mode=Gtk.SelectionMode.SINGLE)
        drawer.set_margin_top(6)
        drawer.set_margin_bottom(6)
        drawer.set_margin_start(6)
        drawer.set_margin_end(6)

        installed_row = Adw.ActionRow(title="Installed",
                                      subtitle="Packages on this system")
        installed_row.set_icon_name("system-software-install-symbolic")
        updates_row = Adw.ActionRow(title="Updates",
                                    subtitle="Packages with updates available")
        updates_row.set_icon_name("software-update-available-symbolic")
        categories_row = Adw.ActionRow(title="Categories",
                                       subtitle="Available packages by category")
        categories_row.set_icon_name("view-grid-symbolic")
        texlive_row = Adw.ActionRow(title="TeX Live",
                                    subtitle="Installed versions")
        texlive_row.set_icon_name("application-x-executable-symbolic")

        self._drawer_installed_row = installed_row
        self._drawer_updates_row = updates_row
        self._drawer_categories_row = categories_row
        self._drawer_texlive_row = texlive_row
        self._package_drawer = drawer

        drawer.append(installed_row)
        drawer.append(updates_row)
        drawer.append(categories_row)
        drawer.append(texlive_row)
        sidebar_box.append(drawer)

        # stores for each view
        self._installed_store = Gio.ListStore.new(PackageItem)
        self._updates_store = Gio.ListStore.new(PackageItem)
        self._categories_store = Gio.ListStore.new(PackageItem)

        # a shared substring filter lets the search entry narrow any view
        self._name_filter = Gtk.StringFilter(
            match_mode=Gtk.StringFilterMatchMode.SUBSTRING)
        self._name_filter.set_expression(
            Gtk.PropertyExpression.new(PackageItem, None, "name"))
        self._installed_fmodel = Gtk.FilterListModel(
            model=self._installed_store, filter=self._name_filter)
        self._updates_fmodel = Gtk.FilterListModel(
            model=self._updates_store, filter=self._name_filter)
        self._categories_fmodel = Gtk.FilterListModel(
            model=self._categories_store, filter=self._name_filter)

        # default to installed
        self._current_fmodel = self._installed_fmodel

        # content: list + bulk action bar
        list_toolbar = Adw.ToolbarView()
        cheader = Adw.HeaderBar()
        # this header is the list page's title bar (not the window's): hide the
        # min/max/close buttons so only the main window keeps them
        cheader.set_show_end_title_buttons(False)
        self.packages_title = Gtk.Label(label="Installed",
                                         css_classes=["heading"])
        cheader.set_title_widget(self.packages_title)

        self._packages_spinner = Gtk.Spinner()
        self._packages_status = Gtk.Label(label="",
                                           css_classes=["dim-label"])
        search = Gtk.SearchEntry(placeholder_text="Filter packages…",
                                 halign=Gtk.Align.END, width_request=220,
                                 tooltip_text="Filter the package list by name")
        search.connect("search-changed", self._on_package_search)
        cheader.pack_end(search)
        cheader.pack_end(self._packages_status)
        cheader.pack_end(self._packages_spinner)

        show_updates = Gtk.Button(label="Update",
                                   icon_name="software-update-available-symbolic",
                                   css_classes=["suggested-action"],
                                   tooltip_text="Show packages with updates "
                                                "available")
        show_updates.connect("clicked", self._on_show_updates)
        cheader.pack_start(show_updates)

        list_toolbar.add_top_bar(cheader)

        scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroll.set_min_content_height(200)
        scroll.set_min_content_width(300)
        scroll.set_size_request(400, 300)
        self.packages_list = Gtk.ListView(
            factory=self._build_package_list_factory(),
            css_classes=[], vexpand=True, hexpand=True)
        self.packages_list.set_show_separators(True)
        self.packages_list.set_size_request(400, 300)
        scroll.set_child(self.packages_list)

        texlive_scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        texlive_scroll.set_min_content_height(200)
        texlive_scroll.set_min_content_width(300)
        texlive_scroll.set_size_request(400, 300)
        texlive_scroll.set_child(self._build_texlive_page())

        self._content_stack = Gtk.Stack()
        self._content_stack.add_named(scroll, "packages")
        self._content_stack.add_named(texlive_scroll, "texlive")
        self._content_stack.set_visible_child_name("packages")
        list_toolbar.set_content(self._content_stack)

        self.selection_bar = Gtk.ActionBar(revealed=False, halign=Gtk.Align.FILL)
        sel_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                          halign=Gtk.Align.CENTER)
        self.selection_label = Gtk.Label(label="0 selected")
        bulk_install = Gtk.Button(label="Install",
                                  css_classes=["suggested-action"],
                                  margin_top=6, margin_bottom=6)
        bulk_install.connect("clicked", self.on_bulk_install)
        bulk_remove = Gtk.Button(label="Remove",
                                 css_classes=["destructive-action"],
                                 margin_top=6, margin_bottom=6)
        bulk_remove.connect("clicked", self.on_bulk_remove)
        sel_box.append(self.selection_label)
        sel_box.append(bulk_install)
        sel_box.append(bulk_remove)
        self.selection_bar.pack_start(sel_box)
        list_toolbar.add_bottom_bar(self.selection_bar)

        # wire drawer selection
        drawer.connect("row-selected", self._on_drawer_row_selected)

        # details page (pushed on double-click / Enter from the list)
        self._details_page = self._build_details_panel()

        # NavigationView: list page (root) <-> details page (with Back button)
        self._nav = Adw.NavigationView()
        list_page = Adw.NavigationPage(child=list_toolbar,
                                       title="Packages", tag="list")
        self._nav.push(list_page)
        self.packages_list.connect("activate", self._on_package_activate)

        split.set_sidebar(Adw.NavigationPage(child=sidebar_box,
                                             title="Browse Packages",
                                             tag="drawer"))
        split.set_content(Adw.NavigationPage(
            child=self._nav, title="Packages", tag="packages"))
        stack.add_titled(split, "packages", "Packages").set_icon_name(
            "system-software-install-symbolic")

    def _build_texlive_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_margin_top(6)
        vbox.set_margin_bottom(6)
        vbox.set_margin_start(6)
        vbox.set_margin_end(6)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                             spacing=12, margin_bottom=6)
        title_lbl = Gtk.Label(label="TeX Live Installations",
                              css_classes=["heading"], xalign=0)
        subtitle_lbl = Gtk.Label(label="", css_classes=["dim-label"],
                                 xalign=0)
        header_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                              spacing=2)
        header_vbox.append(title_lbl)
        header_vbox.append(subtitle_lbl)
        header_box.append(header_vbox)

        self._texlive_sort_btn = Gtk.Button(
            icon_name="view-sort-descending-symbolic",
            tooltip_text="Sort by year")
        self._texlive_sort_btn.connect("clicked", self._on_texlive_sort_clicked)
        header_box.append(self._texlive_sort_btn)

        vbox.append(header_box)

        versions_group = Adw.PreferencesGroup(title="TeX Live Versions")
        self._texlive_listbox = Gtk.ListBox(
            css_classes=["boxed-list"],
            selection_mode=Gtk.SelectionMode.NONE)
        self._texlive_subtitle = Gtk.Label(
            label="Loading versions…",
            css_classes=["dim-label"], xalign=0, margin_top=6)
        versions_group.add(self._texlive_listbox)
        versions_group.add(self._texlive_subtitle)

        vbox.append(versions_group)

        self._texlive_sort_mode = "year"
        self._refresh_texlive_list()

        return vbox

    def _refresh_texlive_list(self):
        listbox = getattr(self, "_texlive_listbox", None)
        if listbox is None:
            return
        child = listbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            listbox.remove(child)
            child = next_child

        installs = self._installations
        primary = self._primary
        multi = len(installs) > 1
        installed_years = {i.year for i in installs if i.year}

        if self._texlive_sort_mode == "installed":
            for inst in installs:
                is_primary = (primary is not None
                              and primary.bin_dir == inst.bin_dir)
                if is_primary:
                    tag = "Primary"
                elif multi:
                    tag = "Detected"
                else:
                    tag = "Active"

                row = Adw.ExpanderRow(
                    title=inst.label,
                    subtitle=f"{tag} — {inst.root}")
                row.add_row(Adw.ActionRow(title="Bin directory",
                                          subtitle=inst.bin_dir))
                row.add_row(Adw.ActionRow(
                    title="Version",
                    subtitle=f"TeX Live {inst.year}" if inst.year else "unknown"))
                row.add_row(Adw.ActionRow(title="Source",
                                          subtitle=inst.source))
                row.add_row(Adw.ActionRow(
                    title="tlmgr",
                    subtitle="yes" if inst.has_tlmgr else "no"))
                row.add_row(Adw.ActionRow(
                    title="Functional",
                    subtitle="yes" if inst.functional else "no (broken)"))
                row.add_row(Adw.ActionRow(
                    title="Engines",
                    subtitle=", ".join(inst.engines) or "none"))
                uninstall_btn = Gtk.Button(
                    label="Uninstall",
                    css_classes=["destructive-action"],
                    tooltip_text=f"Remove {inst.label}")
                uninstall_btn.connect(
                    "clicked",
                    lambda *_b, i=inst: self._confirm_uninstall_texlive(i))
                row.add_suffix(uninstall_btn)
                listbox.append(row)

        def worker():
            years = backend.fetch_available_texlive_years()
            GLib.idle_add(self._finish_refresh_texlive_list, years, installed_years)
        threading.Thread(target=worker, daemon=True).start()

    def _finish_refresh_texlive_list(self, years, installed_years):
        listbox = getattr(self, "_texlive_listbox", None)
        if listbox is None:
            return False
        child = listbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            listbox.remove(child)
            child = next_child

        installs = self._installations
        primary = self._primary
        multi = len(installs) > 1

        all_years = sorted(set(years) | installed_years, reverse=True)
        rows = []

        for year in all_years:
            inst_match = next((i for i in installs if i.year == year), None)
            if inst_match:
                is_primary = (primary is not None
                              and primary.bin_dir == inst_match.bin_dir)
                if is_primary:
                    tag = "Primary"
                elif multi:
                    tag = "Detected"
                else:
                    tag = "Active"

                row = Adw.ExpanderRow(
                    title=inst_match.label,
                    subtitle=f"{tag} — {inst_match.root}")
                row.add_row(Adw.ActionRow(title="Bin directory",
                                          subtitle=inst_match.bin_dir))
                row.add_row(Adw.ActionRow(
                    title="Version",
                    subtitle=f"TeX Live {inst_match.year}" if inst_match.year else "unknown"))
                row.add_row(Adw.ActionRow(title="Source",
                                          subtitle=inst_match.source))
                row.add_row(Adw.ActionRow(
                    title="tlmgr",
                    subtitle="yes" if inst_match.has_tlmgr else "no"))
                row.add_row(Adw.ActionRow(
                    title="Functional",
                    subtitle="yes" if inst_match.functional else "no (broken)"))
                row.add_row(Adw.ActionRow(
                    title="Engines",
                    subtitle=", ".join(inst_match.engines) or "none"))
                uninstall_btn = Gtk.Button(
                    label="Uninstall",
                    css_classes=["destructive-action"],
                    tooltip_text=f"Remove {inst_match.label}")
                uninstall_btn.connect(
                    "clicked",
                    lambda *_b, i=inst_match: self._confirm_uninstall_texlive(i))
                row.add_suffix(uninstall_btn)
                rows.append(row)
            else:
                row = Adw.ActionRow(
                    title=f"TeX Live {year}",
                    subtitle="Available for download")
                install_btn = Gtk.Button(
                    label="Install",
                    css_classes=["suggested-action"],
                    tooltip_text=f"Download and install TeX Live {year}")
                install_btn.connect(
                    "clicked",
                    lambda *_b, y=year: self._on_install_texlive(y))
                row.add_suffix(install_btn)
                rows.append(row)

        if self._texlive_sort_mode == "installed":
            installed_rows = [r for r in rows if isinstance(r, Adw.ExpanderRow)]
            available_rows = [r for r in rows if isinstance(r, Adw.ActionRow)]
            rows = installed_rows + available_rows

        for row in rows:
            listbox.append(row)

        if not installs and not years:
            empty_row = Adw.ActionRow(
                title="No TeX Live versions found",
                subtitle="Install TeX Live to get started")
            listbox.append(empty_row)

        if hasattr(self, "_texlive_subtitle") \
                and self._texlive_subtitle is not None:
            if all_years:
                self._texlive_subtitle.set_label(
                    f"Latest: TeX Live {all_years[0]} — Oldest: TeX Live {all_years[-1]}")
            else:
                self._texlive_subtitle.set_label("No versions found")
        return False

    def _on_texlive_sort_clicked(self, *args):
        if self._texlive_sort_mode == "year":
            self._texlive_sort_mode = "installed"
            self._texlive_sort_btn.set_icon_name("view-sort-ascending-symbolic")
            self._texlive_sort_btn.set_tooltip_text("Sort by installed")
        else:
            self._texlive_sort_mode = "year"
            self._texlive_sort_btn.set_icon_name("view-sort-descending-symbolic")
            self._texlive_sort_btn.set_tooltip_text("Sort by year")
        self._refresh_texlive_list()

    def _on_drawer_row_selected(self, listbox, row):
        if row is None:
            return
        title = row.get_title()
        self.packages_title.set_label(title)
        if title == "TeX Live":
            self._content_stack.set_visible_child_name("texlive")
        elif title == "Installed":
            self._content_stack.set_visible_child_name("packages")
            self._current_fmodel = self._installed_fmodel
        elif title == "Updates":
            self._content_stack.set_visible_child_name("packages")
            self._current_fmodel = self._updates_fmodel
            if not self._updates_loaded:
                self._load_updates_packages()
        else:
            self._content_stack.set_visible_child_name("packages")
            self._current_fmodel = self._categories_fmodel
        if title != "TeX Live":
            self._set_package_model(self._current_fmodel)

    def _build_package_list_factory(self) -> Gtk.SignalListItemFactory:
        """Each row = package name (left) + an Uninstall button (right)."""
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._pkg_row_setup)
        factory.connect("bind", self._pkg_row_bind)
        return factory

    def _pkg_row_setup(self, factory, listitem):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_css_classes(["package-row"])
        row.set_margin_start(10)
        row.set_margin_end(10)
        row.set_margin_top(4)
        row.set_margin_bottom(4)

        icon = Gtk.Image(icon_name="package-x-generic-symbolic",
                         pixel_size=28, valign=Gtk.Align.CENTER,
                         css_classes=["dim-label"])

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name = Gtk.Label(xalign=0, hexpand=True,
                         ellipsize=Pango.EllipsizeMode.MIDDLE,
                         css_classes=["package-name"])
        sub = Gtk.Label(xalign=0, css_classes=["package-sub", "dim-label"],
                        ellipsize=Pango.EllipsizeMode.MIDDLE)
        vbox.append(name)
        vbox.append(sub)

        btn = Gtk.Button(icon_name="user-trash-symbolic",
                         css_classes=["destructive-action", "flat"],
                         tooltip_text="Uninstall this package",
                         valign=Gtk.Align.CENTER)

        row.append(icon)
        row.append(vbox)
        row.append(btn)
        listitem.set_child(row)
        listitem._pkg_name = name
        listitem._pkg_sub = sub
        listitem._pkg_btn = btn
        btn.connect("clicked", lambda *_: self._on_row_action_clicked(listitem))

    def _pkg_row_bind(self, factory, listitem):
        item = listitem.get_item()
        if item is None:
            return
        listitem._pkg_name.set_label(item.name)
        listitem._pkg_sub.set_label(item.category or "")
        if item.update_available:
            # Updates view: show an Update button (no Uninstall)
            btn = listitem._pkg_btn
            btn.set_icon_name("software-update-available-symbolic")
            btn.set_css_classes(["suggested-action", "flat"])
            btn.set_tooltip_text("Update this package")
            btn.set_visible(True)
            btn.set_sensitive(True)
        else:
            btn = listitem._pkg_btn
            btn.set_icon_name("user-trash-symbolic")
            btn.set_css_classes(["destructive-action", "flat"])
            btn.set_tooltip_text("Uninstall this package")
            btn.set_visible(item.installed)
            btn.set_sensitive(item.installed)

    def _on_row_action_clicked(self, listitem):
        item = listitem.get_item()
        if item is None:
            return
        if item.update_available:
            self._confirm_update_package(item.name)
        else:
            self._confirm_uninstall_package(item.name)

    def _confirm_uninstall_package(self, name):
        show_confirm(
            self, "Uninstall package?",
            f"Uninstall {name}?",
            [f"This removes {name} from TeX Live via tlmgr. "
             "This action cannot be undone."],
            lambda: self._uninstall_package(name),
        )

    def _confirm_update_package(self, name):
        show_confirm(
            self, "Update package?",
            f"Update {name}?",
            [f"This updates {name} to the latest version via tlmgr."],
            lambda: self._update_package(name),
        )

    def _update_package(self, name):
        processing = Adw.AlertDialog(heading="Updating…",
                                     body=f"Updating {name}…")
        spinner = Gtk.Spinner(spinning=True)
        spinner.set_margin_top(12)
        processing.set_extra_child(spinner)
        processing.present(self)

        def worker():
            error = None
            try:
                backend.update_package(name)
            except Exception as exc:
                error = str(exc)
                print(f"[DEBUG] _update_package({name}) EXCEPTION:\n{error}",
                      flush=True)
            log_event("_update_package", name,
                      "ok" if error is None else f"ERROR: {error}")
            GLib.idle_add(self._finish_update_package, name, processing, error)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_update_package(self, name, processing, error):
        processing.close()
        if error:
            print(f"[DEBUG] _finish_update_package({name}) FAILED:\n{error}",
                  flush=True)
            dialog = Adw.AlertDialog(heading="Update failed",
                                     body=self._privilege_hint(error))
        else:
            # no longer in the "updates available" list
            store = self._updates_store
            for i in range(store.get_n_items()):
                if store.get_item(i).name == name:
                    store.remove(i)
                    break
            dialog = Adw.AlertDialog(heading="Updated",
                                     body=f"{name} was updated.")
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.present(self)
        return False

    def _set_package_model(self, fmodel):
        """Wrap a filter model in a SingleSelection and track selection."""
        sel = Gtk.SingleSelection.new(fmodel)
        sel.set_autoselect(False)
        sel.connect("selection-changed", self._on_package_selection_changed)
        self.packages_list.set_model(sel)

    def _on_package_selection_changed(self, selection, position, n_items):
        # single click just tracks the current row; details open on activate
        item = selection.get_selected_item()
        self._selected_package = item.name if item is not None else None

    def _on_package_activate(self, listview, position):
        """Double-click / Enter on a row pushes the details page."""
        model = listview.get_model()
        item = model.get_item(position)
        if item is None:
            return
        self._push_package_details(item.name)

    def _build_details_panel(self):
        page = Adw.NavigationPage()
        page.set_title("Package details")
        page.set_tag("details")

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        # this header is the details page's title bar, not the window's:
        # hide the min/max/close buttons and keep only the nav Back button
        header.set_show_end_title_buttons(False)
        self._details_title = Gtk.Label(label="", css_classes=["heading"])
        header.set_title_widget(self._details_title)

        self._details_spinner = Gtk.Spinner()
        header.pack_end(self._details_spinner)

        self._details_uninstall = Gtk.Button(icon_name="user-trash-symbolic",
                                             css_classes=["destructive-action"],
                                             tooltip_text="Uninstall this package")
        self._details_uninstall.connect("clicked", self._on_details_uninstall)
        header.pack_end(self._details_uninstall)
        toolbar.add_top_bar(header)

        clamp = Adw.Clamp(maximum_size=620, margin_top=12, margin_bottom=12)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self._details_desc = Gtk.Label(label="", xalign=0, wrap=True,
                                       selectable=True,
                                       css_classes=["dim-label"])
        vbox.append(self._details_desc)

        meta = Adw.PreferencesGroup(title="Information")
        self._details_cat_row = Adw.ActionRow(title="Category",
                                              subtitle="—")
        self._details_rev_row = Adw.ActionRow(title="Revision",
                                              subtitle="—")
        self._details_path_row = Adw.ActionRow(title="Installed at",
                                               subtitle="—")
        meta.add(self._details_cat_row)
        meta.add(self._details_rev_row)
        meta.add(self._details_path_row)
        vbox.append(meta)

        files_group = Adw.PreferencesGroup(title="Installed files")
        self._details_files_view = Gtk.TextView(editable=False, monospace=True,
                                                css_classes=["terminal"])
        scroll = Gtk.ScrolledWindow(min_content_height=160, vexpand=True)
        scroll.set_child(self._details_files_view)
        files_group.add(scroll)
        vbox.append(files_group)

        clamp.set_child(vbox)
        toolbar.set_content(clamp)
        page.set_child(toolbar)
        return page

    def _push_package_details(self, name):
        """Push the details page (with an automatic Back button)."""
        self._selected_package = name
        self._details_title.set_label(name)
        self._details_spinner.start()
        self._details_uninstall.set_sensitive(False)
        if self._nav.get_visible_page() is not self._details_page:
            self._nav.push(self._details_page)

        def worker():
            info = backend.package_details(name)
            GLib.idle_add(self._finish_package_details, info)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_package_details(self, info):
        self._details_spinner.stop()
        self._details_uninstall.set_sensitive(True)
        self._details_desc.set_label(
            info.get("shortdesc") or info.get("longdesc") or "")
        self._details_cat_row.set_subtitle(info.get("category", "—"))
        self._details_rev_row.set_subtitle(str(info.get("revision", "—")))
        files = info.get("files", [])
        if files:
            try:
                base = (os.path.commonpath(files)
                        if len(files) > 1 else os.path.dirname(files[0]))
            except ValueError:
                base = "—"
            self._details_path_row.set_subtitle(base)
            self._details_files_view.get_buffer().set_text("\n".join(files))
        else:
            self._details_path_row.set_subtitle("—")
            self._details_files_view.get_buffer().set_text("(no file list)")
        return False

    def _on_details_uninstall(self, *args):
        name = self._selected_package
        if not name:
            return
        show_confirm(
            self, "Uninstall package?",
            f"Uninstall {name}?",
            [f"This removes {name} from TeX Live via tlmgr. "
             "This action cannot be undone."],
            lambda: self._uninstall_package(name),
        )

    def _uninstall_package(self, name):
        processing = Adw.AlertDialog(heading="Uninstalling…",
                                     body=f"Removing {name}…")
        spinner = Gtk.Spinner(spinning=True)
        spinner.set_margin_top(12)
        processing.set_extra_child(spinner)
        processing.present(self)

        def worker():
            error = None
            try:
                backend.uninstall_package(name)
            except Exception as exc:
                error = str(exc)
                print(f"[DEBUG] _uninstall_package({name}) EXCEPTION:\n{error}",
                      flush=True)
            log_event("_uninstall_package", name,
                      "ok" if error is None else f"ERROR: {error}")
            GLib.idle_add(self._finish_uninstall_package, name, processing, error)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_uninstall_package(self, name, processing, error):
        processing.close()
        if error:
            print(f"[DEBUG] _finish_uninstall_package({name}) FAILED:\n{error}",
                  flush=True)
            dialog = Adw.AlertDialog(heading="Uninstall failed", body=error)
        else:
            # remove the package from every store that contains it
            for store in (self._installed_store, self._updates_store,
                          self._categories_store):
                for i in range(store.get_n_items()):
                    if store.get_item(i).name == name:
                        store.remove(i)
                        break
            # return to the list view if the details page is open
            if self._nav.get_visible_page() is self._details_page:
                self._nav.pop()
            self._selected_package = None
            self._details_title.set_label("")
            self._details_desc.set_label("")
            self._details_cat_row.set_subtitle("—")
            self._details_rev_row.set_subtitle("—")
            self._details_path_row.set_subtitle("—")
            self._details_files_view.get_buffer().set_text("")
            dialog = Adw.AlertDialog(heading="Uninstalled",
                                     body=f"{name} was removed.")
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.present(self)
        return False

    def _on_package_search(self, entry):
        self._name_filter.set_search(entry.get_text())

    def _on_show_updates(self, *args):
        # jump to the Updates view, which loads the updatable-package list
        self._package_drawer.select_row(self._drawer_updates_row)

    def _select_package_drawer_row(self, title):
        row = None
        if title == "Installed":
            row = self._drawer_installed_row
        elif title == "Updates":
            row = self._drawer_updates_row
        elif title == "Categories":
            row = self._drawer_categories_row
        elif title == "TeX Live":
            row = self._drawer_texlive_row
        if row is not None and self._package_drawer is not None:
            self._package_drawer.select_row(row)

    # ---- Tab 4: Compile & Watch (New Tab 4, A.1, A.2) ----
    def _build_compile_watch(self, stack):
        toolbar = Adw.ToolbarView()
        cheader = Adw.HeaderBar()
        self.status_dot = Gtk.Image(icon_name="radio-symbolic",
                                    css_classes=["dim-label"],
                                    tooltip_text="Idle")
        cheader.pack_start(self.status_dot)
        toolbar.add_top_bar(cheader)

        clamp = Adw.Clamp(maximum_size=800)
        clamp.set_margin_top(12)
        clamp.set_margin_bottom(12)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        group = Adw.PreferencesGroup(title="Compile &amp; Watch")
        file_row = Adw.ActionRow(title="Root .tex file",
                                 subtitle="No file selected")
        browse = Gtk.Button(label="Browse…")
        browse.connect("clicked", self.on_browse_file)
        file_row.add_suffix(browse)
        group.add(file_row)

        engine = Adw.ComboRow(title="Engine",
                              model=Gtk.StringList.new(
                                  ["pdflatex", "xelatex", "lualatex"]))
        group.add(engine)

        actions = Adw.ActionRow(title="Actions")
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        check = Gtk.Button(label="Check Dependencies")
        check.connect("clicked", self.on_check_dependencies)
        watch = Gtk.Button(label="Start Watching",
                           css_classes=["suggested-action"])
        watch.connect("clicked", self.on_start_watch)
        pdf = Gtk.Button(label="Open PDF")
        pdf.connect("clicked", self.on_open_pdf)
        action_box.append(check)
        action_box.append(watch)
        action_box.append(pdf)
        actions.add_suffix(action_box)
        group.add(actions)
        vbox.append(group)

        live = Gtk.ScrolledWindow(min_content_height=180, vexpand=True)
        self.live_log_view = Gtk.TextView(editable=False, monospace=True,
                                          css_classes=["terminal"])
        live.set_child(self.live_log_view)
        vbox.append(live)

        report = Adw.ExpanderRow(title="Compile Report", expanded=False)
        report.add_row(Adw.ActionRow(title="No report yet"))
        vbox.append(report)

        clamp.set_child(vbox)
        toolbar.set_content(clamp)
        stack.add_titled(toolbar, "compile", "Compile &amp; Watch").set_icon_name(
            "media-playback-start-symbolic")

    # ---- Utilities (E.2, E.3) ----
    def _build_utilities(self, stack):
        clamp = Adw.Clamp(maximum_size=700)
        clamp.set_margin_top(12)
        clamp.set_margin_bottom(12)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        bib = Adw.PreferencesGroup(title="Bibliography")
        bib_row = Adw.ActionRow(title="Validate .bib file",
                                subtitle="Check duplicate keys and missing "
                                         "fields")
        bib_btn = Gtk.Button(label="Choose…")
        bib_btn.connect("clicked", self.on_validate_bib)
        bib_row.add_suffix(bib_btn)
        bib.add(bib_row)
        vbox.append(bib)

        path = Adw.PreferencesGroup(title="Path Repair")
        path_row = Adw.ActionRow(title="Symlink / PATH Doctor",
                                 subtitle="Find broken symlinks to TeX "
                                          "binaries")
        path_btn = Gtk.Button(label="Scan")
        path_btn.connect("clicked", self.on_scan_symlinks)
        path_row.add_suffix(path_btn)
        path.add(path_row)
        vbox.append(path)

        history = Adw.PreferencesGroup(title="History Log")
        history_row = Adw.ActionRow(title="Installation history",
                                    subtitle="Commands run by TeXManager")
        history_btn = Gtk.Button(label="View")
        history_btn.connect("clicked", self.on_view_history)
        history_row.add_suffix(history_btn)
        history.add(history_row)
        vbox.append(history)

        clamp.set_child(vbox)
        stack.add_titled(clamp, "utilities", "Utilities").set_icon_name(
            "preferences-system-symbolic")

    # ---- package data ----
    def _populate_packages(self):
        # categories / available (sample)
        for name, category in [
            ("beamer", "Presentation"),
            ("listings", "Source Code"),
            ("hyperref", "Hyperlinks"),
            ("geometry", "Page Layout"),
            ("microtype", "Typography"),
            ("siunitx", "Units"),
            ("csquotes", "Quotations"),
            ("booktabs", "Tables"),
        ]:
            self._categories_store.append(PackageItem(name, installed=False,
                                                       category=category))

        # the Installed view is filled from the real TeX Live install;
        # the Updates view is filled lazily when its drawer row is selected
        self._set_package_model(self._installed_fmodel)
        self._load_installed_packages()

    def _load_installed_packages(self):
        """Load the real installed packages off the UI thread."""
        self._packages_spinner.start()
        self._packages_status.set_label("Loading installed packages…")

        def worker():
            names = backend.list_installed_packages()
            GLib.idle_add(self._finish_load_installed, names)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_load_installed(self, names):
        self._installed_store.remove_all()
        for name in names:
            self._installed_store.append(PackageItem(name, installed=True,
                                                     category="TeX Live"))
        self._packages_spinner.stop()
        self._packages_status.set_label(f"{len(names)} installed")
        log_event("package-list", "installed", f"count={len(names)}")
        return False

    def _load_updates_packages(self):
        """Load packages with available updates off the UI thread."""
        self._packages_spinner.start()
        self._packages_status.set_label("Loading updates…")

        def worker():
            names = backend.list_updatable_packages()
            GLib.idle_add(self._finish_load_updates, names)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_load_updates(self, names):
        self._updates_store.remove_all()
        for name in names:
            self._updates_store.append(PackageItem(
                name, installed=True, category="TeX Live",
                update_available=True))
        self._packages_spinner.stop()
        self._packages_status.set_label(f"{len(names)} updates available")
        self._updates_loaded = True
        log_event("package-list", "updates", f"count={len(names)}")
        return False

    def _populate_shortcuts(self):
        shortcuts = Gtk.ShortcutsWindow()
        section = Gtk.ShortcutsSection()
        group = Gtk.ShortcutsGroup(title="General")
        quit_sc = Gtk.ShortcutsShortcut(title="Quit", action_name="app.quit")
        pref_sc = Gtk.ShortcutsShortcut(title="Preferences",
                                        action_name="app.preferences")
        group.add_shortcut(quit_sc)
        group.add_shortcut(pref_sc)
        section.add_group(group)
        shortcuts.add_section(section)
        self.set_help_overlay(shortcuts)

    # ---- installation detection (backend) ----
    def _refresh_installation_status(self):
        self._primary, self._installations, conflict = detect()
        self._refresh_texlive_list()
        if self._primary is None:
            self.status_row.set_subtitle("No installation detected")
            self.status_icon.set_from_icon_name("dialog-warning-symbolic")
            self.status_icon.set_css_classes(["warning"])
            self.conflict_banner.set_revealed(False)
            return
        if conflict:
            n = len(self._installations)
            self.status_row.set_subtitle(
                f"{n} installations — using {self._primary.label}")
            self.conflict_banner.set_title(
                f"{n} TeX Live installations detected")
            self.conflict_banner.set_revealed(True)
        else:
            self.status_row.set_subtitle(self._primary.label)
            self.conflict_banner.set_revealed(False)
        self.status_icon.set_from_icon_name("emblem-ok-symbolic")
        self.status_icon.set_css_classes(["success"])
        log_event("_refresh_installation_status",
                  f"installs={len(self._installations)} "
                  f"primary={self._primary.label if self._primary else 'none'} "
                  f"conflict={self.conflict_banner.get_revealed()}")

    def on_show_details(self, *args):
        win = Gtk.Window(title="Installation Details")
        win.set_transient_for(self)
        win.set_default_size(560, 600)
        win.set_resizable(True)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        close = Gtk.Button(label="Close")
        close.connect("clicked", lambda *_: win.close())
        header.pack_end(close)
        toolbar.add_top_bar(header)

        clamp = Adw.Clamp(margin_top=16, margin_bottom=16,
                          margin_start=16, margin_end=16)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        suggestion = self._build_suggestion()
        if suggestion:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                           css_classes=["card"], margin_bottom=6)
            card.set_margin_top(6)
            card.set_margin_start(6)
            card.set_margin_end(6)
            card.append(Gtk.Label(label="Suggestion", xalign=0,
                                  css_classes=["heading"]))
            card.append(Gtk.Label(label=suggestion, xalign=0, wrap=True,
                                  selectable=True))
            vbox.append(card)
        listbox = Gtk.ListBox(css_classes=["boxed-list"],
                              selection_mode=Gtk.SelectionMode.NONE)
        multi = len(self._installations) > 1
        for inst in self._installations:
            is_primary = (self._primary is not None
                          and self._primary.bin_dir == inst.bin_dir)
            if is_primary:
                tag = "Primary"
            elif multi:
                tag = "Conflicting"
            else:
                tag = "Active"
            row = Adw.ExpanderRow(title=inst.label, subtitle=tag)
            if multi:
                uninstall_btn = Gtk.Button(
                    label="Uninstall",
                    css_classes=["destructive-action"],
                    tooltip_text=f"Uninstall {inst.label}")
                uninstall_btn.connect(
                    "clicked",
                    lambda *_b, i=inst: self._confirm_uninstall(i, win))
                row.add_suffix(uninstall_btn)
            row.add_row(Adw.ActionRow(title="Root", subtitle=inst.root))
            row.add_row(Adw.ActionRow(title="Bin directory",
                                     subtitle=inst.bin_dir))
            row.add_row(Adw.ActionRow(
                title="Year", subtitle=str(inst.year) if inst.year else "unknown"))
            row.add_row(Adw.ActionRow(title="Source", subtitle=inst.source))
            row.add_row(Adw.ActionRow(
                title="tlmgr", subtitle="yes" if inst.has_tlmgr else "no"))
            row.add_row(Adw.ActionRow(
                title="Functional",
                subtitle="yes" if inst.functional else "no (broken)"))
            row.add_row(Adw.ActionRow(
                title="Engines",
                subtitle=", ".join(inst.engines) or "none"))
            listbox.append(row)
        vbox.append(listbox)
        scrolled = Gtk.ScrolledWindow(vexpand=True,
                                     min_content_height=320,
                                     max_content_height=600)
        scrolled.set_child(vbox)
        clamp.set_child(scrolled)
        toolbar.set_content(clamp)
        win.set_child(toolbar)
        win.present()

    def _build_suggestion(self):
        installs = self._installations
        if not installs:
            return ("No TeX installation was found. Install TeX Live to compile "
                    "documents.")
        if len(installs) == 1:
            inst = installs[0]
            if inst.functional:
                return (f"You have a single, working installation "
                        f"({inst.label}). No action needed.")
            return (f"A TeX installation was found at {inst.root} but it is not "
                    f"functional. Reinstall or repair it before compiling.")

        rec = self._primary
        others = [i for i in installs if i is not rec]
        parts = []
        if rec is not None:
            parts.append(
                f"Use {rec.label} as the primary (newest, tlmgr-managed, "
                f"easiest to update).")
        other_desc = ", ".join(o.label for o in others)
        parts.append(
            f"The other detected installation(s) — {other_desc} — share the same "
            f"engines on your PATH and can cause format/package conflicts.")
        if rec is not None and rec.has_tlmgr and any(not o.has_tlmgr for o in others):
            parts.append(
                "Avoid mixing tlmgr-managed and distro (apt) TeX Live: pick one "
                "package manager. To keep the upstream install, remove the distro "
                "one with: sudo apt remove 'texlive-*'.")
        parts.append(
            "Consider removing the older/duplicate installs so a single TeX Live "
            "owns your PATH, then re-run detection.")
        return " ".join(parts)

    # ---- uninstall (conflict cleanup) ----
    def _confirm_uninstall(self, inst, details_dialog):
        if inst.source == "distro" or inst.root == "/usr":
            detail = ("This will run: pkexec apt-get remove --purge -y "
                      "'texlive-*' to uninstall the distro (apt) TeX Live.")
        else:
            detail = (f"This will remove the directory via: "
                      f"pkexec rm -rf {inst.root}")
        show_confirm(
            details_dialog,
            "Uninstall installation?",
            f"Uninstall {inst.label}?",
            [detail, "This action cannot be undone."],
            lambda: self._uninstall_installation(inst, details_dialog),
        )

    def _confirm_uninstall_texlive(self, inst):
        self._confirm_uninstall(inst, self)

    def _uninstall_installation(self, inst, details_dialog):
        if details_dialog is not None and details_dialog is not self:
            details_dialog.close()

        processing = Adw.AlertDialog(heading="Uninstalling…",
                                      body=f"Removing {inst.label}…")
        spinner = Gtk.Spinner(spinning=True)
        spinner.set_margin_top(12)
        spinner.set_size_request(32, 32)
        processing.set_extra_child(spinner)
        processing.present(self)

        def worker():
            error = None
            try:
                if inst.source == "distro" or inst.root == "/usr":
                    cmd = ["pkexec", "apt-get", "remove", "--purge", "-y",
                           "texlive-*"]
                else:
                    if not inst.root.startswith(_SAFE_TUG_PREFIXES):
                        raise RuntimeError(
                            f"Refusing to uninstall unsafe path: {inst.root}")
                    cmd = ["pkexec", "rm", "-rf", inst.root]
                if shutil.which("pkexec") is None:
                    cmd = cmd[1:]
                cmd_str = " ".join(cmd)
                result = subprocess.run(cmd, capture_output=True, text=True,
                                        timeout=300)
                rc = result.returncode
                log_event("_uninstall_installation", cmd_str,
                          f"returncode={rc}; "
                          f"stdout={result.stdout[:500]}; "
                          f"stderr={result.stderr[:500]}")
                if rc != 0:
                    raise RuntimeError(result.stderr or result.stdout
                                      or "Uninstall command failed")
            except Exception as exc:
                error = str(exc)
                log_event("_uninstall_installation", str(inst.label),
                          f"ERROR: {exc}")
            GLib.idle_add(self._finish_uninstall, inst, processing, error)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_uninstall(self, inst, processing, error):
        processing.close()
        self._refresh_installation_status()
        if error:
            self._show_uninstall_result(False, error, inst)
        else:
            self._show_uninstall_result(True, "", inst)
        return False

    def _show_uninstall_result(self, success, error, inst):
        dialog = Adw.AlertDialog(
            heading="Uninstall " + ("complete" if success else "failed"),
            body=(f"{inst.label} was uninstalled."
                  if success else
                  f"Could not uninstall {inst.label}:\n{error}"),
        )
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.present(self)

    # ---- handlers (UI only; backend TODO) ----
    def on_resolve_conflict(self, *args):  # A.3
        if not self._installations:
            self.conflict_banner.set_revealed(False)
            return
        n = len(self._installations)
        alert = Adw.AlertDialog(
            heading="Resolve installation conflict",
            body=(
                f"TeXManager detected {n} TeX installations on this machine. "
                "Resolving lets you choose which one is used as the primary for "
                "compiling and package management. The other installation(s) stay "
                "on disk but will not be used by TeXManager. Continue?"
            ),
        )
        alert.add_response("cancel", "Cancel")
        alert.add_response("continue", "Continue")
        alert.set_response_appearance(
            "continue", Adw.ResponseAppearance.SUGGESTED)
        alert.set_default_response("continue")
        alert.set_close_response("cancel")
        alert.connect(
            "response",
            lambda d, r: self._open_conflict_picker()
            if r == "continue" else None)
        alert.present(self)

    def _open_conflict_picker(self):
        dialog = Adw.Dialog()
        dialog.set_title("Resolve Conflict")
        dialog.set_content_width(460)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        done = Gtk.Button(label="Use selected",
                          css_classes=["suggested-action"])
        header.pack_end(done)
        toolbar.add_top_bar(header)

        clamp = Adw.Clamp(margin_top=16, margin_bottom=16,
                          margin_start=16, margin_end=16)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.append(Gtk.Label(
            label=f"{len(self._installations)} TeX installations were found on "
                  "this machine. TeXManager can only use one as primary. "
                  "Select it below, then press “Use selected”.",
            xalign=0, wrap=True))

        listbox = Gtk.ListBox(css_classes=["boxed-list"],
                              selection_mode=Gtk.SelectionMode.NONE)
        self._conflict_radios = []
        group = None
        for inst in self._installations:
            row = Adw.ActionRow(title=inst.label, subtitle=inst.bin_dir)
            radio = Gtk.CheckButton()
            if group is not None:
                radio.set_group(group)
            else:
                group = radio
            if self._primary is not None \
                    and self._primary.bin_dir == inst.bin_dir:
                radio.set_active(True)
            row.add_prefix(radio)
            listbox.append(row)
            self._conflict_radios.append((radio, inst))
        vbox.append(listbox)

        scrolled = Gtk.ScrolledWindow(vexpand=True,
                                     min_content_height=240,
                                     max_content_height=480)
        scrolled.set_child(vbox)
        clamp.set_child(scrolled)
        toolbar.set_content(clamp)
        dialog.set_child(toolbar)
        done.connect("clicked", lambda *_: self._apply_conflict_choice(dialog))
        dialog.present(self)

    def _apply_conflict_choice(self, dialog):
        for radio, inst in self._conflict_radios:
            if radio.get_active():
                self._primary = inst
                break
        self._refresh_installation_status()
        self.conflict_banner.set_revealed(False)
        dialog.close()

    def on_expand_report(self, *args):  # A.1
        pass

    def on_explain_install(self, *args):  # D.2
        pass

    def on_bulk_install(self, *args):  # D.1
        pass

    def on_bulk_remove(self, *args):  # D.1
        pass

    def on_browse_file(self, *args):  # New Tab 4
        pass

    def on_check_dependencies(self, *args):  # A.2
        pass

    def on_start_watch(self, *args):  # New Tab 4
        pass

    def on_open_pdf(self, *args):  # New Tab 4
        pass

    def _on_install_texlive(self, year: int):
        wizard = OnboardingWindow(transient_for=self, year=year)
        wizard.present()

    def _on_texlive_sort_clicked(self, *args):
        if self._texlive_sort_mode == "year":
            self._texlive_sort_mode = "installed"
            self._texlive_sort_btn.set_icon_name("view-sort-ascending-symbolic")
            self._texlive_sort_btn.set_tooltip_text("Sort by installed")
        else:
            self._texlive_sort_mode = "year"
            self._texlive_sort_btn.set_icon_name("view-sort-descending-symbolic")
            self._texlive_sort_btn.set_tooltip_text("Sort by year")
        self._refresh_texlive_list()

    def on_validate_bib(self, *args):  # E.2
        pass

    def on_scan_symlinks(self, *args):  # E.3
        pass

    def on_view_history(self, *args):
        from .history import read_history
        text = read_history() or "(no history yet)"
        win = Gtk.Window(title="Installation History")
        win.set_transient_for(self)
        win.set_default_size(640, 480)
        win.set_resizable(True)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        close = Gtk.Button(label="Close")
        close.connect("clicked", lambda *_: win.close())
        header.pack_end(close)
        toolbar.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        view = Gtk.TextView(editable=False, monospace=True,
                            css_classes=["terminal"])
        view.get_buffer().set_text(text)
        scroll.set_child(view)
        toolbar.set_content(scroll)
        win.set_child(toolbar)
        win.present()
