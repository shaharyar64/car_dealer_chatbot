"""One-command project setup (Windows, macOS and Linux).

    python scripts/setup.py

1. Creates .env from .env.example if it doesn't exist, then stops so you can edit it.
2. Checks that OPENAI_API_KEY in .env is filled in.
3. Creates the .venv virtual environment and installs the project with its dependencies.

Safe to run again at any time.
Uses only the standard library, so it runs with any Python 3.10+ before anything is installed.
"""

import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
VENV_DIR = ROOT / ".venv"
REQUIRED = {
    "OPENAI_API_KEY": "your OpenAI API key (starts with sk-)",
}
PLACEHOLDERS = ("your_", "sk-your-api-key-here")


def step(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def fail(message: str) -> None:
    print(f"\nSetup stopped: {message}", file=sys.stderr)
    sys.exit(1)


def read_env(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser (python-dotenv isn't installed yet)."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def check_env() -> None:
    step("Checking .env")
    if not ENV_FILE.exists():
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        fail(
            "created .env from .env.example.\n"
            "Open .env, fill in OPENAI_API_KEY, then run this command again."
        )
    values = read_env(ENV_FILE)
    missing = [
        f"  {key}: {hint}"
        for key, hint in REQUIRED.items()
        if not values.get(key) or any(p in values[key] for p in PLACEHOLDERS)
    ]
    if missing:
        fail(
            "please fill in these values in .env, then run this command again:\n"
            + "\n".join(missing)
        )
    print("OK")


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(*args: object) -> None:
    result = subprocess.run([str(a) for a in args], cwd=ROOT)
    if result.returncode != 0:
        fail(f"command failed: {' '.join(str(a) for a in args)}")


def main() -> None:
    if sys.version_info < (3, 10):
        fail(f"Python 3.10+ is required (this is {sys.version.split()[0]}).")

    check_env()

    step("Creating virtual environment (.venv)")
    if venv_python().exists():
        print("Already exists")
    else:
        venv.create(VENV_DIR, with_pip=True)
        print("Created")

    step("Installing the project and its dependencies (this can take a minute)")
    run(venv_python(), "-m", "pip", "install", "--quiet", "--upgrade", "pip")
    run(venv_python(), "-m", "pip", "install", "--quiet", "-e", ".[dev]")
    print("Installed")

    python = venv_python().relative_to(ROOT)
    print(
        "\nAll set! Start the web app with:\n"
        f"    {python} -m streamlit run src/car_dealer_chatbot/webapp.py\n"
        "Run the tests with:\n"
        f"    {python} -m pytest"
    )


if __name__ == "__main__":
    main()
