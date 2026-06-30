import subprocess
import sys


def main() -> int:
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
