"""Wrapper helpers that expose simple functions from the existing download scripts.

These wrappers import the project's top-level scripts and provide
convenience functions to download galleries programmatically.
"""
from threading import Event
from typing import Optional
import os
import download_images as core
import download_images_scrolled as scrolled

def download_gallery(gallery_url: str, output_dir: Optional[str] = None, stop_event: Optional[Event] = None) -> int:
    if stop_event is None:
        stop_event = Event()
    if output_dir is None:
        default = core.get_gallery_name(gallery_url) or "Private"
        output_dir = core.make_output_dir(os.path.join("Private", default))
    return core.download_gallery(gallery_url, output_dir, stop_event)


def download_gallery_scrolled(gallery_url: str, output_dir: Optional[str] = None, stop_event: Optional[Event] = None, **kwargs) -> int:
    if stop_event is None:
        stop_event = Event()
    if output_dir is None:
        default = scrolled.get_gallery_name(gallery_url) or "Private"
        output_dir = scrolled.make_output_dir(os.path.join("Private", default))
    return scrolled.download_gallery_scrolled(gallery_url, output_dir, stop_event, **kwargs)
