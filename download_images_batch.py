import argparse
import subprocess
import sys
from pathlib import Path


def read_links_file(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as file:
        lines = [line.strip() for line in file]
    return [line for line in lines if line and not line.startswith("#")]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run download_images.py once per link listed in a links file."
    )
    parser.add_argument(
        "--links-file",
        default="Private/readme.txt",
        help="Path to a text file containing one gallery URL per line.",
    )
    parser.add_argument(
        "--script",
        default="download_images.py",
        help="Path to the download_images.py script to invoke.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue processing remaining links even if one invocation fails.",
    )
    args = parser.parse_args()

    root = Path.cwd()
    links_path = (root / args.links_file).resolve()

    script_path = Path(args.script)
    if not script_path.is_absolute():
        local_script = Path(__file__).resolve().parent / args.script
        cwd_script = root / args.script
        script_path = cwd_script if cwd_script.exists() else local_script
    script_path = script_path.resolve()

    if not links_path.exists():
        print(f"Links file not found: {links_path}")
        return 1
    if not script_path.exists():
        print(f"Script not found: {script_path}")
        return 1

    links = read_links_file(links_path)
    if not links:
        print(f"No links found in: {links_path}")
        return 1

    for index, url in enumerate(links, start=1):
        print(f"[{index}/{len(links)}] Running download_images.py for: {url}")
        result = subprocess.run([sys.executable, str(script_path), url], cwd=str(root))
        if result.returncode != 0:
            print(
                f"download_images.py failed for {url} with exit code {result.returncode}."
            )
            if not args.continue_on_error:
                return result.returncode

    print("All links processed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
