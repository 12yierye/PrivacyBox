import sys
sys.dont_write_bytecode = True

from privacybox.cli.app import app

if __name__ == "__main__":
    app()
