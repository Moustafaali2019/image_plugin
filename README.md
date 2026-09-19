# image_plugin

Lightweight plugin that exposes the project's gallery download scripts as a small Python package and includes a simple test for Hugging Face image classification.

Contents

- `download_images.py` — main static gallery downloader (CLI).
- `download_images_scrolled.py` — browser-scrolling variant (Selenium) (CLI).
- `download_images_batch.py` — run `download_images.py` for multiple links (CLI).
- `image_plugin/wrappers.py` — programmatic wrappers: `download_gallery(...)`, `download_gallery_scrolled(...)`.
- `test_image.py` — quick test harness that runs a Hugging Face `image-classification` pipeline.

Installation

1. Create a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\\Scripts\\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

Usage

- Command-line examples:

```bash
python download_images.py https://example.com/channel/ ./out
python download_images_scrolled.py https://example.com/channel/ ./out --scroll-max 100
python download_images_batch.py --links-file Private/readme.txt
```

- Programmatic (import the plugin):

```python
from image_plugin import download_gallery

download_gallery('https://example.com/gallery/1234', output_dir='./out')
```

- Run the Hugging Face test script:

```bash
python test_image.py                # uses a default sample image URL
python test_image.py path_or_url    # test a local image path or remote URL
```

Notes

- `download_images_scrolled.py` requires Selenium and `webdriver-manager` for automatic driver handling. Install the extras from `requirements.txt` and ensure Chrome (or another supported browser) is available on the system.
- The wrappers in `image_plugin/wrappers.py` rely on the top-level scripts being importable from the project root. Run code from the repository root or adjust `PYTHONPATH` accordingly.
- For large-scale or headless scraping, respect site terms of service and robots.txt.

Contributions

Feel free to open issues or add improvements. Suggested next steps: add unit tests, a CLI entrypoint for the plugin, and better logging and retry behavior for downloads.
