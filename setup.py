import sys

from tw_alpha_scraper.cli import main


LEGACY_COMMANDS = {
    "add": ["accounts", "add"],
    "manual-add": ["accounts", "manual-add"],
    "login": ["accounts", "login"],
    "list": ["accounts", "list"],
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python setup.py [add|manual-add|login|list]")
        raise SystemExit(1)

    mapped = LEGACY_COMMANDS.get(sys.argv[1].lower())
    if mapped is None:
        print(f"Unknown command: {sys.argv[1]}")
        raise SystemExit(1)

    raise SystemExit(main(mapped))
