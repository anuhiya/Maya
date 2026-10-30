"""Put the demo back to its start: python scripts/reset_demo.py --yes"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maya import site  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="confirm the reset")
    if not parser.parse_args().yes:
        print("Nothing done. Run with --yes to reset the site, database (with its fingerprints) and uploads.")
        return 1
    site.reset()
    print("Reset done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
