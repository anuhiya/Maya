"""Put the demo back to its start: python scripts/reset_demo.py --yes [--empty]

--yes alone resets the site, the database (with its fingerprints), the custom versions and the uploads.
--empty does the same and also leaves every findings page empty until the agent has run once, so an audience
watches the findings appear. Employees, company policy, the policy site (v1 and v2 published, v3 held back) and the
saved runs in data/replays are kept either way.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maya import site, state  # noqa: E402


def main(argv=None, cfg=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="confirm the reset")
    parser.add_argument("--empty", action="store_true", help="also keep every findings page empty until the agent runs")
    args = parser.parse_args(argv)
    if not args.yes:
        print("Nothing done. Run with --yes to reset the site, database (with its fingerprints) and uploads.")
        return 1
    cfg = cfg or site.load_config()
    site.reset(cfg)
    if args.empty:
        state.set_empty(cfg)
        print("Reset done. The demo is empty: reload the browser page, then run the agent.")
    else:
        print("Reset done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
