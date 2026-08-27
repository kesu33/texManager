import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import shutil
import subprocess
from pathlib import Path

from gi.repository import GObject, GLib, Gio, Gtk, Adw  # noqa: E402

from .detection import TexInstallation, detect  # noqa: E402
from .dialogs import show_confirm  # noqa: E402
from .history import log_event  # noqa: E402
from .models import PackageItem, TemplateItem  # noqa: E402

_SAFE_TUG_PREFIXES = ("/usr/local/texlive", "/opt/texlive",
                     str(Path.home() / "texlive"))


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

        self._primary: TexInstallation | None = None
        self._installations: list[TexInstallation] = []
        self._conflict_radios: list = []

        self._build_ui()
        self._populate_packages()
        self._populate_shortcuts()
        self._refresh_installation_status()

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

    # ---- sample data ----
    def _populate_packages(self):
        store = Gio.ListStore.new(PackageItem)
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
        group.add_shortcut(quit_sc)
        group.add_shortcut(pref_sc)
        section.add_group(group)
        shortcuts.add_section(section)
        self.set_help_overlay(shortcuts)

    # ---- installation detection (backend) ----
    def _refresh_installation_status(self):
        self._primary, self._installations, conflict = detect()
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
        dialog = Adw.Dialog()
        dialog.set_title("Installation Details")
        dialog.set_content_width(520)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        close = Gtk.Button(label="Close")
        close.connect("clicked", lambda *_: dialog.close())
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
                    lambda *_b, i=inst: self._confirm_uninstall(i, dialog))
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
        dialog.set_child(toolbar)
        dialog.present(self)

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
            self,
            "Uninstall installation?",
            f"Uninstall {inst.label}?",
            [detail, "This action cannot be undone."],
            lambda: self._uninstall_installation(inst, details_dialog),
        )

    def _uninstall_installation(self, inst, details_dialog):
        details_dialog.close()
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
            log_event("_uninstall_installation", str(inst.label),
                      f"ERROR: {exc}")
            self._show_uninstall_result(False, str(exc), inst)
            return
        self._refresh_installation_status()
        self._show_uninstall_result(True, "", inst)

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

    def on_validate_bib(self, *args):  # E.2
        pass

    def on_scan_symlinks(self, *args):  # E.3
        pass

    def on_view_history(self, *args):
        from .history import read_history
        text = read_history() or "(no history yet)"
        dialog = Adw.Dialog()
        dialog.set_title("Installation History")
        dialog.set_content_width(640)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        close = Gtk.Button(label="Close")
        close.connect("clicked", lambda *_: dialog.close())
        header.pack_end(close)
        toolbar.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=360,
                                    max_content_height=600)
        view = Gtk.TextView(editable=False, monospace=True,
                            css_classes=["terminal"])
        view.get_buffer().set_text(text)
        scroll.set_child(view)
        toolbar.set_content(scroll)
        dialog.set_child(toolbar)
        dialog.present(self)
