import argparse
import os
import re
import sys
from threading import Event, Thread
from urllib.parse import urljoin, urlparse
import time

import requests
from bs4 import BeautifulSoup
from typing import Optional, List

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


def extract_gallery_links(index_url: str) -> List[str]:
    response = requests.get(index_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    gallery_urls = []
    for item in soup.select("ul.wookmark-initialised li.thumbwook"):
        link = item.find("a", class_="rel-link")
        if not link:
            continue
        href = link.get("href")
        if not href:
            continue
        full_url = urljoin(index_url, href)
        # skip non-gallery links (affiliate/outsider links)
        if "/galleries/" not in full_url:
            continue
        gallery_urls.append(full_url)

    unique_urls = list(dict.fromkeys(gallery_urls))
    return unique_urls


def create_scrolled_driver():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError as exc:
        raise RuntimeError(
            "Selenium and webdriver-manager are required for _scrolled mode. "
            "Install with: pip install selenium webdriver-manager"
        ) from exc

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")

    try:
        # Prefer Selenium Manager (Selenium 4.10+) to auto-resolve a driver
        return webdriver.Chrome(options=options)
    except Exception:
        # Fallback to webdriver-manager when Selenium Manager is not available
        return webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )


def get_scrolled_page_source(
    url: str,
    max_scrolls: int = 200,
    pause: float = 1.0,
    item_selector: str = "li.thumbwook",
    click_selectors: Optional[List[str]] = None,
    verbose: bool = False,
) -> str:
    driver = create_scrolled_driver()
    try:
        driver.get(url)
        time.sleep(pause)
        if click_selectors is None:
            click_selectors = [
                "button.load-more",
                "button.load_more",
                ".loadmore",
                "a.load-more",
                "a.load_more",
                "#loadmore",
            ]

        prev_count = driver.execute_script(
            "return document.querySelectorAll(arguments[0]).length", item_selector
        )
        best_count = prev_count
        best_source = driver.page_source

        stable_rounds = 0
        for i in range(max_scrolls):
            # perform stepped scrolling across the page to trigger lazy loads
            driver.execute_script(
                "var step=window.innerHeight; for(var y=0;y<document.body.scrollHeight;y+=step){window.scrollTo(0,y);} window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(pause)

            # try clicking common load-more buttons
            clicked_any = False
            for sel in click_selectors:
                try:
                    clicked = driver.execute_script(
                        "var el=document.querySelector(arguments[0]); if(el){el.click(); return true;} return false;",
                        sel,
                    )
                except Exception:
                    clicked = False
                if clicked:
                    clicked_any = True
                    time.sleep(pause)

            # ensure last item is in view
            driver.execute_script(
                "let items=document.querySelectorAll(arguments[0]); if(items.length) items[items.length-1].scrollIntoView();",
                item_selector,
            )
            time.sleep(pause)

            new_count = driver.execute_script(
                "return document.querySelectorAll(arguments[0]).length", item_selector
            )

            if new_count >= best_count:
                best_count = new_count
                best_source = driver.page_source

            if verbose:
                print(f"scroll iter={i+1} items={new_count} clicked={clicked_any} best={best_count}")

            if new_count == prev_count and not clicked_any:
                stable_rounds += 1
                if stable_rounds >= 2:
                    break
            else:
                stable_rounds = 0

            prev_count = new_count

        time.sleep(pause)
        return best_source
    finally:
        driver.quit()


def extract_gallery_links_scrolled(
    index_url: str,
    max_scrolls: int = 50,
    pause: float = 1.0,
    click_selectors: Optional[List[str]] = None,
    item_selector: str = "li.thumbwook",
 ) -> List[str]:
    page_source = get_scrolled_page_source(
        index_url,
        max_scrolls=max_scrolls,
        pause=pause,
        item_selector=item_selector,
        click_selectors=click_selectors,
    )
    soup = BeautifulSoup(page_source, "html.parser")

    gallery_urls = []
    for item in soup.select("ul.wookmark-initialised li.thumbwook"):
        link = item.find("a", class_="rel-link")
        if not link:
            continue
        href = link.get("href")
        if not href:
            continue
        full_url = urljoin(index_url, href)
        gallery_urls.append(full_url)

    unique_urls = list(dict.fromkeys(gallery_urls))
    return unique_urls


def extract_image_urls(gallery_url: str) -> List[str]:
    try:
        response = requests.get(gallery_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        print(f"Skipping gallery (failed to fetch): {gallery_url} -> {exc}")
        return []
    soup = BeautifulSoup(response.text, "html.parser")

    image_urls = []
    for item in soup.select("ul.wookmark-initialised li.thumbwook"):
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
    return unique_urls


def extract_image_urls_scrolled(
    gallery_url: str,
    max_scrolls: int = 50,
    pause: float = 1.0,
    click_selectors: Optional[List[str]] = None,
    item_selector: str = "li.thumbwook",
 ) -> List[str]:
    try:
        page_source = get_scrolled_page_source(
            gallery_url,
            max_scrolls=max_scrolls,
            pause=pause,
            item_selector=item_selector,
            click_selectors=click_selectors,
        )
    except Exception as exc:
        print(f"Skipping gallery (failed during scrolling): {gallery_url} -> {exc}")
        return []
    soup = BeautifulSoup(page_source, "html.parser")

    image_urls = []
    for item in soup.select("ul.wookmark-initialised li.thumbwook"):
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
        return 0

    make_output_dir(output_dir)

    downloaded = 0
    for image_url in image_urls:
        if stop_event.is_set():
            break

        filename = get_filename_from_url(image_url)
        # Skip non-JPG files
        if not filename.lower().endswith(".jpg"):
            continue

        dest_path = os.path.join(output_dir, filename)
        if os.path.exists(dest_path):
            continue

        if download_file(image_url, dest_path):
            downloaded += 1

    return downloaded


def download_gallery_scrolled(
    gallery_url: str,
    output_dir: str,
    stop_event: Event,
    max_scrolls: int = 50,
    pause: float = 1.0,
    click_selectors: Optional[List[str]] = None,
    item_selector: str = "li.thumbwook",
) -> int:
    image_urls = extract_image_urls_scrolled(
        gallery_url,
        max_scrolls=max_scrolls,
        pause=pause,
        click_selectors=click_selectors,
        item_selector=item_selector,
    )
    if not image_urls:
        return 0

    make_output_dir(output_dir)

    downloaded = 0
    for image_url in image_urls:
        if stop_event.is_set():
            break

        filename = get_filename_from_url(image_url)
        # Skip non-JPG files
        if not filename.lower().endswith(".jpg"):
            continue

        dest_path = os.path.join(output_dir, filename)
        if os.path.exists(dest_path):
            continue

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
        description="Download image galleries from an index page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python download_images_scrolled.py https://example.com/channel/ ./out\n"
            "  python download_images_scrolled.py https://example.com/channel/ ./out --scroll-max 200 --scroll-pause 1.5 --click-selector \".loadmore\" --item-selector \"li.thumbwook\"\n\n"
            "Notes:\n"
            "  - This scrolled script uses Selenium; install with: pip install selenium webdriver-manager\n"
            "  - Use --click-selector multiple times to provide multiple selectors\n"
            "  - If thumbnails use a different element than the default, set --item-selector\n"
        ),
    )
    parser.add_argument(
        "url",
        help="Index URL containing gallery thumbnails (e.g. https://example.com/channels/istripper/)",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=None,
        help=(
            "Output directory for downloaded images (defaults to Private/<last-path-segment>), "
            "or provide an absolute path like E:\\downloads"
        ),
    )
    parser.add_argument(
        "--max-galleries",
        type=int,
        default=0,
        help="Limit the number of galleries to download (0 = all)",
    )
    parser.add_argument(
        "--scrolled",
        action="store_true",
        help="Use browser rendering and scrolling to load additional content (enabled by default in this script)",
    )
    parser.add_argument(
        "--scroll-max",
        type=int,
        default=50,
        help="Maximum number of scroll iterations to attempt (increase for very long index pages)",
    )
    parser.add_argument(
        "--scroll-pause",
        type=float,
        default=1.0,
        help="Seconds to wait after each scroll/interaction; increase for slow-loading sites",
    )
    parser.add_argument(
        "--click-selector",
        action="append",
        default=None,
        help="CSS selector for a 'load more' or similar control to click (can be repeated). "
        "Example: --click-selector '.loadmore'",
    )
    parser.add_argument(
        "--item-selector",
        default="li.thumbwook",
        help=(
            "CSS selector for gallery thumbnail items (used to detect new items when scrolling). "
            "Adjust if thumbnails are in a different element."
        ),
    )
    parser.add_argument(
        "--scroll-galleries",
        action="store_true",
        help="Also use scrolling when extracting images from each gallery page. If omitted, gallery pages are parsed statically.",
    )
    args = parser.parse_args()

    # This script is the scrolled variant — enable scrolled mode by default
    args.scrolled = True

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
        if args.scrolled:
            gallery_urls = extract_gallery_links_scrolled(
                args.url,
                max_scrolls=args.scroll_max,
                pause=args.scroll_pause,
                click_selectors=args.click_selector,
            )
        else:
            gallery_urls = extract_gallery_links(args.url)

        if args.max_galleries > 0:
            gallery_urls = gallery_urls[: args.max_galleries]

        total_downloaded = 0
        for idx, gallery_url in enumerate(gallery_urls, 1):
            if stop_event.is_set():
                print("Stop requested; ending downloads after current gallery.")
                break
            if args.scroll_galleries:
                count = download_gallery_scrolled(
                    gallery_url,
                    output_dir,
                    stop_event,
                    max_scrolls=args.scroll_max,
                    pause=args.scroll_pause,
                    click_selectors=args.click_selector,
                    item_selector=args.item_selector,
                )
            else:
                count = download_gallery(gallery_url, output_dir, stop_event)
            total_downloaded += count
            if count > 0:
                print(f"[{idx}/{len(gallery_urls)}] Gallery processed. Downloaded {count} jpg images from this gallery.")

        print(f"Done. Total downloaded images: {total_downloaded}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
