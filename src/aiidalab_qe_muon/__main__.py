from aiida.common.exceptions import NotExistent
import subprocess
from aiida.orm import load_code
from aiida import load_profile
import shutil
import click

"""
Automatic installation of the pythonjob code, needed to run undi.

So we only setup in AiiDA.
"""


@click.group()
def cli():
    pass


@cli.command(help="Setup python3@localhost in the current AiiDA database.")
def setup_python():
    load_profile()
    try:
        load_code("python3@localhost")
    except NotExistent:
        # Use shutil.which to find the path of the phonopy executable
        python_path = shutil.which("python3")
        if not python_path:
            raise FileNotFoundError(
                "python3 code is not found in PATH"
            )
        # Construct the command as a list of arguments
        command = [
            "verdi",
            "code",
            "create",
            "core.code.installed",
            "--non-interactive",
            "--label",
            "python3",
            "--default-calc-job-plugin",
            "pythonjob.pythonjob",
            "--computer",
            "localhost",
            "--filepath-executable",
            python_path,
        ]

        # Use subprocess.run to run the command
        subprocess.run(command, check=True)
    else:
        print("Code python3@localhost is already installed! Nothing to do here.")


if __name__ == "__main__":
    cli()
