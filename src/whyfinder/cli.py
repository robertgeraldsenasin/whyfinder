"""Command-line entry point: `whyfinder`.

Commands are added milestone by milestone (docs/plan/ROADMAP.md): `data` (M0), `build` and
`eval`/`gate` (M1), `explain` (M2), `index` (M3), `export` and `serve` (M4).
"""

import typer

from whyfinder import __version__

app = typer.Typer(help="Whyfinder: find your next game. Know why.", no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.callback()
def main() -> None:
    """Whyfinder command line."""
