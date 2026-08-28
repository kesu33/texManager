#!/usr/bin/env python3
"""Dev entry point for TeXManager (UI-first prototype).

Run directly:  python3 main.py
The full GUI requires GTK4 + libadwaita-1 and PyGObject to be installed.
"""
import sys


def main():
    try:
        from texmanager import TexManagerApplication
    except ValueError as exc:
        if "Namespace Gtk" in str(exc) or "Namespace Adw" in str(exc):
            print(
                "ERROR: GTK4 / libadwaita not found on this system.\n"
                "Install the runtime and Python bindings, e.g.:\n\n"
                "  sudo apt-get install libgtk-4-1 gir1.2-gtk-4.0 \\\n"
                "       libadwaita-1-0 gir1.2-adw-1 python3-gi\n",
                file=sys.stderr,
            )
            return 1
        raise
    try:
        return TexManagerApplication().run(sys.argv)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
