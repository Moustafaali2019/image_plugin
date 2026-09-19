#!/usr/bin/env python3
"""Simple test script that runs a Hugging Face image-classification model.

Usage:
  python test_image.py [image_path_or_url]

If no argument is provided, a default sample image URL will be used.
"""
import sys
from typing import List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    img = argv[0] if argv else "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/tasks/image_classification.png"

    try:
        import transformers
        # try normal export first
        if hasattr(transformers, "pipeline"):
            from transformers import pipeline  # type: ignore
        else:
            # fallback to package submodule
            try:
                from transformers.pipelines import pipeline  # type: ignore
            except Exception as subexc:
                print("Installed `transformers` does not expose `pipeline`.")
                print("transformers.__version__:", getattr(transformers, "__version__", "unknown"))
                print("Consider upgrading with: pip install --upgrade transformers")
                print("Detailed error:", subexc)
                return 2
    except Exception as exc:
        print("Missing dependency: transformers (and backend libs). Install with: pip install -r requirements.txt")
        print(exc)
        return 2

    try:
        classifier = pipeline("image-classification", model="google/vit-base-patch16-224")
        results = classifier(img)
        print("Results:")
        for r in results:
            print(f"{r['label']}: {r['score']:.4f}")
        return 0
    except Exception as exc:
        print("Failed to run image-classification pipeline:")
        print(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
