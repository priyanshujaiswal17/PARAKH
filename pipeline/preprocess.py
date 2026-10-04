"""Image preprocessing module: EXIF stripping, blur detection & enhancement, aspect-preserving downscaling."""

from __future__ import annotations

import io
import logging
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from config import settings

logger = logging.getLogger("label_reader.preprocess")

DEFAULT_BLUR_THRESHOLD = 80.0


def enhance_blurry_image(img: Image.Image) -> Image.Image:
    """Enhances a blurry or low-contrast image to maximize text legibility for vision models."""
    try:
        # 1. Normalize dynamic range / contrast across lighting conditions
        enhanced = ImageOps.autocontrast(img, cutoff=1)

        # 2. Apply unsharp masking to recover edge gradients
        enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=2.0, percent=160, threshold=2))

        # 3. Boost fine stroke sharpness
        enhancer = ImageEnhance.Sharpness(enhanced)
        enhanced = enhancer.enhance(1.5)

        # 4. Slight contrast boost for faint ink
        c_enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = c_enhancer.enhance(1.15)

        return enhanced
    except Exception as exc:
        logger.warning("Image deblurring enhancement failed: %s, falling back to original", exc)
        return img


def preprocess_image(
    image: Image.Image,
    backend: str = "gemini",
    blur_threshold: float = DEFAULT_BLUR_THRESHOLD,
) -> tuple[bytes, list[str]]:
    """Preprocesses a PIL Image for model ingestion.
    
    1. Transposes orientation according to EXIF and converts to RGB.
    2. Checks sharpness and dimensions, producing non-blocking warnings.
    3. If blurry, applies unsharp mask, contrast stretching, and edge enhancement.
    4. Resizes so longest side is at most max_side (preserving aspect ratio with Lanczos).
    5. Re-encodes as high-quality JPEG without any EXIF metadata.
    """
    warnings: list[str] = []

    # 1. Orientation & RGB conversion
    img = ImageOps.exif_transpose(image)
    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size

    # Check shorter side
    if min(w, h) < 600:
        warnings.append("Image is small, text may be unreadable.")

    # Check sharpness: variance of FIND_EDGES filter (excluding border convolution artifacts)
    is_blurry = False
    try:
        edge_img = img.convert("L").filter(ImageFilter.FIND_EDGES)
        edge_array = np.array(edge_img, dtype=np.float32)[2:-2, 2:-2]
        variance = float(np.var(edge_array))
        if variance < blur_threshold:
            is_blurry = True
            warnings.append("Image appears blurry — applied edge sharpening & contrast enhancement.")
    except Exception as exc:
        logger.debug("Sharpness check skipped due to error: %s", exc)

    # Automatic deblurring and contrast enhancement
    if is_blurry:
        img = enhance_blurry_image(img)
    else:
        try:
            img = ImageOps.autocontrast(img, cutoff=0.5)
        except Exception:
            pass

    # 2. Resizing based on limits
    max_side = settings.max_side_online

    if max(w, h) > max_side:
        scale = max_side / float(max(w, h))
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 3. Re-encode as high-quality JPEG (without EXIF)
    jpeg_quality = 95 if is_blurry else 90
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality)
    jpeg_bytes = buf.getvalue()

    return jpeg_bytes, warnings


def preprocess_images(
    images: list[Image.Image],
    backend: str = "gemini",
    blur_threshold: float = DEFAULT_BLUR_THRESHOLD,
) -> tuple[list[bytes], list[str]]:
    """Preprocesses multiple images and collects all deduplicated warnings."""
    all_bytes: list[bytes] = []
    all_warnings: list[str] = []

    for idx, img in enumerate(images):
        jpeg_bytes, warns = preprocess_image(img, backend=backend, blur_threshold=blur_threshold)
        all_bytes.append(jpeg_bytes)
        for w in warns:
            prefix = f"Photo {idx + 1}: " if len(images) > 1 else ""
            msg = f"{prefix}{w}"
            if msg not in all_warnings:
                all_warnings.append(msg)

    return all_bytes, all_warnings
