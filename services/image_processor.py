"""
Image Validation and Radiographic Preprocessing Pipeline (PRD FR-03, Section 5.1.4).
Validates file type, file size, and image integrity, applies CLAHE contrast enhancement,
and extracts quantitative anatomical zone densities for downstream VLM report generation.

Cloud note: in addition to writing files to disk (local convenience), the original and
CLAHE-processed images are also returned as in-memory byte strings so they can be stored
in the database for hosted deployments with ephemeral disk storage.
"""
import io
import os
import uuid
import numpy as np
import cv2
from PIL import Image, UnidentifiedImageError

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_FILE_SIZE_BYTES = 16 * 1024 * 1024  # 16 MB


class ImageValidationError(ValueError):
    """Raised when an uploaded file fails type, size, or radiographic integrity checks."""
    pass


def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower().strip()
    return ext in ALLOWED_EXTENSIONS


def validate_and_preprocess_xray(file_stream_or_path, original_filename: str, upload_dir: str) -> dict:
    """
    Validates an uploaded chest X-ray image, saves the original and CLAHE-preprocessed
    images to disk, and extracts anatomical zone metrics.

    Returns a dictionary containing:
      - image_rel_path: relative static path to original saved image
      - processed_rel_path: relative static path to CLAHE-preprocessed image
      - orig_bytes: in-memory bytes of the sanitized original image
      - proc_bytes: in-memory bytes of the CLAHE-preprocessed image (PNG)
      - metrics: dictionary of quantitative radiographic features
    """
    if not original_filename:
        raise ImageValidationError("No image file was provided. Please select a chest X-ray image (JPG, JPEG, or PNG).")

    if not allowed_file(original_filename):
        ext = original_filename.rsplit(".", 1)[1].upper() if "." in original_filename else "UNKNOWN"
        raise ImageValidationError(
            f"Unsupported file format ({ext}). Please upload a valid chest X-ray image in JPG, JPEG, or PNG format (DICOM support is planned for a future release)."
        )

    os.makedirs(upload_dir, exist_ok=True)

    # Read bytes from path or file-like stream
    if isinstance(file_stream_or_path, str):
        if not os.path.exists(file_stream_or_path):
            raise ImageValidationError("Selected image file could not be found on disk.")
        with open(file_stream_or_path, "rb") as f:
            raw_bytes = f.read()
    else:
        file_stream_or_path.seek(0)
        raw_bytes = file_stream_or_path.read()

    if len(raw_bytes) == 0:
        raise ImageValidationError("The uploaded file is empty (0 bytes). Please upload a valid chest X-ray image.")

    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        size_mb = len(raw_bytes) / (1024 * 1024)
        raise ImageValidationError(
            f"File size ({size_mb:.1f} MB) exceeds the 16.0 MB maximum limit. Please compress or resize the image."
        )

    # Verify image header integrity with Pillow
    try:
        verify_img = Image.open(io.BytesIO(raw_bytes))
        verify_img.verify()
    except (UnidentifiedImageError, Exception) as exc:
        raise ImageValidationError(
            "Invalid or corrupted image file. The uploaded file could not be decoded as a valid JPG or PNG image."
        ) from exc

    # Re-open image for pixel processing
    pil_img = Image.open(io.BytesIO(raw_bytes))
    orig_width, orig_height = pil_img.size
    if orig_width < 64 or orig_height < 64:
        raise ImageValidationError(
            f"Image resolution ({orig_width}x{orig_height} px) is too small for chest X-ray analysis. Minimum required resolution is 64x64 px."
        )

    # Check color saturation to determine if grayscale radiograph vs RGB color image
    rgb_arr = np.array(pil_img.convert("RGB"), dtype=np.float32)
    channel_diff = np.mean(np.max(rgb_arr, axis=2) - np.min(rgb_arr, axis=2))
    is_grayscale_like = bool(channel_diff < 18.0)

    # Convert to grayscale for radiographic pipeline
    gray_pil = pil_img.convert("L")
    gray_np = np.array(gray_pil, dtype=np.uint8)

    # Save standardized original image
    unique_token = uuid.uuid4().hex[:12]
    ext = original_filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = "png"
    saved_orig_name = f"cxr_orig_{unique_token}.{ext}"
    saved_proc_name = f"cxr_clahe_{unique_token}.png"

    orig_abs_path = os.path.join(upload_dir, saved_orig_name)
    proc_abs_path = os.path.join(upload_dir, saved_proc_name)

    # Save original image (converted to RGB/L clean format to strip any unsafe EXIF metadata - Section 7 Privacy)
    clean_orig = pil_img.convert("RGB") if not is_grayscale_like else gray_pil
    clean_orig.save(orig_abs_path)

    # Capture in-memory original bytes (same clean, EXIF-stripped content)
    orig_buf = io.BytesIO()
    clean_orig.save(orig_buf, format="PNG" if ext == "png" else "JPEG")
    orig_bytes = orig_buf.getvalue()

    # Preprocessing pipeline: Resize to 512x512 canonical tensor grid + CLAHE contrast enhancement
    canonical_size = (512, 512)
    resized_gray = cv2.resize(gray_np, canonical_size, interpolation=cv2.INTER_AREA)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    clahe_img = clahe.apply(resized_gray)

    # Save CLAHE enhanced image at original aspect ratio (capped at 900px max dim for fast web rendering)
    max_dim = 900
    scale = min(1.0, max_dim / max(orig_width, orig_height))
    disp_w, disp_h = int(orig_width * scale), int(orig_height * scale)
    disp_gray = cv2.resize(gray_np, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
    disp_clahe = clahe.apply(disp_gray)
    disp_clahe_img = Image.fromarray(disp_clahe, mode="L")
    disp_clahe_img.save(proc_abs_path, format="PNG")

    # Capture in-memory processed (CLAHE) bytes
    proc_buf = io.BytesIO()
    disp_clahe_img.save(proc_buf, format="PNG")
    proc_bytes = proc_buf.getvalue()

    # Compute anatomical zone density metrics on the 512x512 canonical radiograph
    norm = resized_gray.astype(np.float32) / 255.0
    # Anatomical regions in PA view:
    # Right Upper Zone (RUZ): y in [0.16..0.46], x in [0.16..0.44]
    # Right Lower Zone (RLZ): y in [0.46..0.74], x in [0.16..0.44]
    # Left Upper Zone (LUZ):  y in [0.16..0.46], x in [0.56..0.84]
    # Left Lower Zone (LLZ):  y in [0.46..0.74], x in [0.56..0.84]
    H, W = norm.shape
    ruz = float(np.mean(norm[int(0.16 * H):int(0.46 * H), int(0.16 * W):int(0.44 * W)]))
    rlz = float(np.mean(norm[int(0.46 * H):int(0.74 * H), int(0.16 * W):int(0.44 * W)]))
    luz = float(np.mean(norm[int(0.16 * H):int(0.46 * H), int(0.56 * W):int(0.84 * W)]))
    llz = float(np.mean(norm[int(0.46 * H):int(0.74 * H), int(0.56 * W):int(0.84 * W)]))

    # Costophrenic angle regions (basal lateral corners)
    rcp = float(np.mean(norm[int(0.62 * H):int(0.78 * H), int(0.14 * W):int(0.32 * W)]))
    lcp = float(np.mean(norm[int(0.62 * H):int(0.78 * H), int(0.68 * W):int(0.86 * W)]))

    # Central cardiac / lower mediastinal zone (shifted slightly to anatomical left, viewer right)
    cardiac_zone = norm[int(0.44 * H):int(0.74 * H), int(0.28 * W):int(0.76 * W)]
    # Estimate Cardiothoracic Ratio (CTR) from horizontal profile at mid-lower thorax
    profile_row = np.mean(norm[int(0.54 * H):int(0.66 * H), int(0.15 * W):int(0.85 * W)], axis=0)
    lung_min = float(np.percentile(profile_row, 20))
    heart_max = float(np.percentile(profile_row, 90))
    thresh = lung_min + 0.52 * (heart_max - lung_min)
    cardiac_fraction = float(np.mean(profile_row > thresh))
    estimated_ctr = round(float(np.clip(0.39 + 0.34 * cardiac_fraction, 0.41, 0.64)), 2)

    # Hemithorax symmetry (100% = identical mean density between right and left lung fields)
    right_mean = (ruz + rlz) / 2.0
    left_mean = (luz + llz) / 2.0
    asymmetry = abs(right_mean - left_mean)
    symmetry_score = round(float(np.clip((1.0 - asymmetry * 2.2) * 100.0, 55.0, 99.4)), 1)

    metrics = {
        "original_filename": original_filename,
        "dimensions": f"{orig_width} × {orig_height} px",
        "file_size_kb": round(len(raw_bytes) / 1024.0, 1),
        "is_grayscale_radiograph": is_grayscale_like,
        "mean_intensity": round(float(np.mean(gray_np)), 1),
        "std_contrast": round(float(np.std(gray_np)), 1),
        "preprocessing_pipeline": "512×512 Canonical Resample + CLAHE (clip=2.2, grid=8×8) + EXIF Sanitization",
        "zones": {
            "right_upper_zone": round(ruz, 3),
            "right_lower_zone": round(rlz, 3),
            "left_upper_zone": round(luz, 3),
            "left_lower_zone": round(llz, 3),
            "right_costophrenic": round(rcp, 3),
            "left_costophrenic": round(lcp, 3),
        },
        "estimated_ctr": estimated_ctr,
        "lung_symmetry_pct": symmetry_score,
        "cardiac_mean_density": round(float(np.mean(cardiac_zone)), 3),
    }

    return {
        "image_rel_path": f"uploads/{saved_orig_name}",
        "processed_rel_path": f"uploads/{saved_proc_name}",
        "orig_bytes": orig_bytes,
        "proc_bytes": proc_bytes,
        "metrics": metrics,
    }
