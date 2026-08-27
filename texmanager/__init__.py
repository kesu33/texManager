import os
import sys

from .application import TexManagerApplication

__all__ = ["TexManagerApplication"]


def main():
    app = TexManagerApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
