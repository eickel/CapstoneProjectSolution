"""Application entry point."""

from src.cli.menu import CLIApp


def main() -> None:
    app = CLIApp()
    app.run()


if __name__ == "__main__":
    main()
