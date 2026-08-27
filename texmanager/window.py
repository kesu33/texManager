import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GObject, GLib, Gio, Gtk, Adw  # noqa: E402

from .models import PackageItem, TemplateItem  # noqa: E402


PACKAGE_ROW_FACTORY = b"""
<interface>
  <template class="GtkListItem">
    <object class="GtkBox">
      <property name="spacing">12</property>
      <property name="margin-start">12</property>
      <property name="margin-end">12</property>
      <child>
        <object class="GtkCheckButton" id="check"/>
      </child>
      <child>
        <object class="GtkLabel">
          <property name="xalign">0</property>
          <property name="hexpand">1</property>
          <binding name="label">
            <lookup name="name" type="PackageItem">
              <lookup name="item">GtkListItem</lookup>
            </lookup>
          </binding>
        </object>
      </child>
    </object>
  </template>
</interface>
"""

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


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("TeXManager")
        self.set_default_size(1000, 720)

        self._build_ui()
        self._populate_packages()
        self._populate_shortcuts()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        switcher_title = Adw.ViewSwitcherTitle(title="TeXManager",
                                               subtitle="TeX Live Manager")
        header.set_title_widget(switcher_title)

        switcher = Adw.ViewSwitcher(stack=switcher_title.get_stack(),
                                    policy=Adw.ViewSwitcherPolicy.WIDE)
        header.pack_start(switcher)

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
        switcher_title.set_stack(stack)
        toolbar.set_content(stack)

        self._build_overview(stack)
        self._build_packages(stack)
        self._build_compile_watch(stack)
        self._build_utilities(stack)

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
        status_row = Adw.ActionRow(title="TeX Installation",
                                   subtitle="No installation detected")
        status_icon = Gtk.Image(icon_name="dialog-warning-symbolic",
                                css_classes=["warning"])
        status_row.add_suffix(status_icon)
        status_group.add(status_row)
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

        # sidebar: Explain panel
        explain_status = Adw.StatusPage(icon_name="info-symbolic",
                                        title="Explain This Package",
                                        description="Select a single package "
                                                    "to see details.")
        explain_clamp = Adw.Clamp(maximum_size=420)
        self.explain_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                   spacing=12, visible=False)
        self.explain_name = Gtk.Label(xalign=0)
        self.explain_desc = Gtk.Label(xalign=0, wrap=True)
        self.explain_deps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                    spacing=6)
        self.explain_install = Gtk.Button(label="Install", halign=Gtk.Align.CENTER,
                                          css_classes=["suggested-action"])
        self.explain_install.connect("clicked", self.on_explain_install)
        self.explain_box.append(self.explain_name)
        self.explain_box.append(self.explain_desc)
        self.explain_box.append(self.explain_deps)
        self.explain_box.append(self.explain_install)
        explain_clamp.set_child(self.explain_box)
        explain_status.set_child(explain_clamp)
        split.set_sidebar(Adw.NavigationPage(child=explain_status,
                                             title="Package Details",
                                             tag="explain"))

        # content: list + bulk action bar
        list_toolbar = Adw.ToolbarView()
        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.packages_list = Gtk.ListView(factory=_list_factory(PACKAGE_ROW_FACTORY),
                                          css_classes=["boxed-list"])
        scroll.set_child(self.packages_list)
        list_toolbar.set_content(scroll)

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

        split.set_content(Adw.NavigationPage(
            child=list_toolbar, title="Packages", tag="packages"))
        stack.add_titled(split, "packages", "Packages").set_icon_name(
            "system-software-install-symbolic")

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

        group = Adw.PreferencesGroup(title="Compile & Watch")
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
        stack.add_titled(toolbar, "compile", "Compile & Watch").set_icon_name(
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

        clamp.set_child(vbox)
        stack.add_titled(clamp, "utilities", "Utilities").set_icon_name(
            "preferences-system-symbolic")

    # ---- sample data ----
    def _populate_packages(self):
        store = GObject.ListStore.new(PackageItem)
        for name in ("latex-base", "graphicx", "tikz", "biblatex", "fontspec"):
            store.append(PackageItem(name))
        self.packages_list.set_model(Gtk.NoSelection(model=store))

    def _populate_shortcuts(self):
        shortcuts = Gtk.ShortcutsWindow()
        section = Gtk.ShortcutsSection()
        group = Gtk.ShortcutsGroup(title="General")
        quit_sc = Gtk.ShortcutsShortcut(title="Quit", action_name="app.quit")
        pref_sc = Gtk.ShortcutsShortcut(title="Preferences",
                                        action_name="app.preferences")
        group.add(quit_sc)
        group.add(pref_sc)
        section.add(group)
        shortcuts.add(section)
        self.set_help_overlay(shortcuts)

    # ---- handlers (UI only; backend TODO) ----
    def on_resolve_conflict(self, *args):  # A.3
        self.conflict_banner.set_revealed(False)

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

    def on_validate_bib(self, *args):  # E.2
        pass

    def on_scan_symlinks(self, *args):  # E.3
        pass
