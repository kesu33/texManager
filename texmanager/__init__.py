import os
import sys

from .application import TexManagerApplication

__all__ = ["TexManagerApplication"]


def main():
    app = TexManagerApplication()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
