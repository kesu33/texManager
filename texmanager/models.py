import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GObject  # noqa: E402


class PackageItem(GObject.Object):
    """A single CTAN/TeX Live package shown in the Packages list (D.1/D.2)."""

    __gtype_name__ = "PackageItem"

    name = GObject.Property(type=str, default="")
    installed = GObject.Property(type=bool, default=True)
    selected = GObject.Property(type=bool, default=False)
    category = GObject.Property(type=str, default="")

    def __init__(self, name: str, installed: bool = True, category: str = ""):
        super().__init__()
        self.name = name
        self.installed = installed
        self.category = category


class TemplateItem(GObject.Object):
    """A project template shown in the New Project grid (E.1)."""

    __gtype_name__ = "TemplateItem"

    name = GObject.Property(type=str, default="")
    description = GObject.Property(type=str, default="")

    def __init__(self, name: str, description: str):
        super().__init__()
        self.name = name
        self.description = description
