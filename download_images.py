import argparse
import os
import re
import sys
from threading import Event, Thread
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}


def make_output_dir(path: str) -> str:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path


def sanitize_filename(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()


def download_file(url: str, dest_path: str) -> bool:
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(dest_path, "wb") as out_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        out_file.write(chunk)
        return True
    except Exception as exc:
        print(f"Failed to download {url}: {exc}")
        return False


def extract_gallery_links(index_url: str) -> list[str]:
    print(f"Fetching gallery index page: {index_url}")
    response = requests.get(index_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    gallery_urls = []
    for item in soup.find_all("li", class_="thumbwook"):
        link = item.find("a", class_="rel-link")
        if not link:
            continue
        href = link.get("href")
        if not href:
            continue
        full_url = urljoin(index_url, href)
        gallery_urls.append(full_url)

    unique_urls = list(dict.fromkeys(gallery_urls))
    print(f"Found {len(unique_urls)} gallery links")
    return unique_urls


def extract_image_urls(gallery_url: str) -> list[str]:
    print(f"Fetching gallery page: {gallery_url}")
    response = requests.get(gallery_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    image_urls = []
    for item in soup.find_all("li", class_="thumbwook"):
        img = item.find("img")
        if not img:
            continue
        url = img.get("data-src") or img.get("src")
        if not url:
            continue
        if url.startswith("//"):
            url = "https:" + url
        image_urls.append(url)

    unique_urls = list(dict.fromkeys(image_urls))
    print(f"Found {len(unique_urls)} image URLs")
    return unique_urls


def get_gallery_name(gallery_url: str) -> str:
    parsed = urlparse(gallery_url)
    path = parsed.path.rstrip("/")
    name = os.path.basename(path) or parsed.netloc
    return sanitize_filename(name)


def get_filename_from_url(image_url: str) -> str:
    parsed = urlparse(image_url)
    name = os.path.basename(parsed.path)
    return sanitize_filename(name) or "image.jpg"


def download_gallery(gallery_url: str, output_dir: str, stop_event: Event) -> int:
    image_urls = extract_image_urls(gallery_url)
    if not image_urls:
        print(f"No images found in gallery: {gallery_url}")
        return 0

    make_output_dir(output_dir)

    downloaded = 0
    for image_url in image_urls:
        if stop_event.is_set():
            print("Stop requested; ending gallery after current file.")
            break

        filename = get_filename_from_url(image_url)
        dest_path = os.path.join(output_dir, filename)
        if os.path.exists(dest_path):
            print(f"Skipping existing file: {dest_path}")
            downloaded += 1
            continue

        print(f"Downloading {image_url}")
        if download_file(image_url, dest_path):
            downloaded += 1

    return downloaded


def wait_for_enter(stop_event: Event) -> None:
    try:
        input()
        stop_event.set()
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download image galleries from an index page."
    )
    parser.add_argument("url", help="Index URL containing gallery thumbnails")
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=None,
        help="Output directory for downloaded images (defaults to the URL's last path segment)",
    )
    parser.add_argument(
        "--max-galleries",
        type=int,
        default=0,
        help="Limit the number of galleries to download (0 = all)",
    )
    args = parser.parse_args()

    if args.output_dir:
        output_dir = make_output_dir(args.output_dir)
    else:
        default_dir = get_gallery_name(args.url) or "Private"
        output_dir = make_output_dir(os.path.join("Private", default_dir))

    stop_event = Event()
    watcher = Thread(target=wait_for_enter, args=(stop_event,), daemon=True)
    watcher.start()
    print("Press Enter to stop after the current image download finishes.")

    try:
        gallery_urls = extract_gallery_links(args.url)
        if args.max_galleries > 0:
            gallery_urls = gallery_urls[: args.max_galleries]

        total_downloaded = 0
        for gallery_url in gallery_urls:
            if stop_event.is_set():
                print("Stop requested; ending downloads after current gallery.")
                break
            total_downloaded += download_gallery(gallery_url, output_dir, stop_event)

        print(f"Done. Total downloaded images: {total_downloaded}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
