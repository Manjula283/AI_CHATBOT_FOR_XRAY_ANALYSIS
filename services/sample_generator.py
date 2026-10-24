"""
Synthetic Clinical Chest Radiograph (CXR) Phantom Generator.
Creates realistic high-resolution PA chest X-ray phantom images for sample testing
and demo pre-seeding without requiring external dataset downloads.
"""
import os
import numpy as np
import cv2
from PIL import Image, ImageDraw


def _create_base_thorax(size=800, seed=42, cardiomegaly=False, rll_opacity=False,
                        bilateral_effusion=False, lul_opacity=False):
    rng = np.random.default_rng(seed)
    h, w = size, size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ny = (yy - h * 0.5) / (h * 0.5)  # -1 to 1
    nx = (xx - w * 0.5) / (w * 0.5)  # -1 to 1

    # Base radiographic film background (dark outside body)
    img = np.full((h, w), 12.0, dtype=np.float32)

    # Smooth continuous neck-to-shoulder-to-torso contour
    # Width transitions smoothly from neck (0.21) at top to shoulder/thorax (0.77)
    neck_to_shoulder = 1.0 / (1.0 + np.exp(-(ny + 0.62) / 0.055))
    half_width = 0.21 * (1.0 - neck_to_shoulder) + (0.79 - 0.07 * (ny ** 2)) * neck_to_shoulder
    # Smooth lateral falloff at body edge
    edge_softness = np.clip((half_width - np.abs(nx)) / 0.045, 0.0, 1.0)
    center_thickness = np.clip(1.0 - (np.abs(nx) / (half_width + 1e-4)) ** 2.2, 0.0, 1.0)
    img += edge_softness * (78.0 + 52.0 * center_thickness)

    # Spine & Mediastinum central column (radiopaque)
    spine_width = 0.072 + 0.015 * np.exp(-((ny + 0.1) ** 2) / 0.3)
    spine_profile = np.exp(-((nx / spine_width) ** 2))
    vertebrae_mod = 0.89 + 0.11 * np.cos(ny * 46.0)
    img += spine_profile * vertebrae_mod * 68.0

    # Trachea & Carina bifurcation (radiolucent air column in upper mediastinum)
    trachea_env = np.clip(1.0 - np.exp((ny + 0.14) / 0.04), 0.0, 1.0)
    trachea_profile = np.exp(-(((nx - 0.004) / 0.026) ** 2)) * trachea_env
    img -= trachea_profile * 40.0

    # Right & Left Lung Fields (radiolucent aerated cavities)
    # Anatomical RIGHT is on viewer's LEFT (nx < 0); Anatomical LEFT is on viewer's RIGHT (nx > 0)
    rl_cx, rl_cy = -0.295, -0.04
    rl_rx = 0.245 * (1.0 + 0.23 * np.tanh((ny - rl_cy) * 1.85))
    rl_ry = 0.555
    rl_dist = ((nx - rl_cx) / np.clip(rl_rx, 0.08, 0.4)) ** 2 + ((ny - rl_cy) / rl_ry) ** 2
    r_diaphragm_y = 0.43 + 0.15 * ((nx - rl_cx) / 0.25) ** 2
    if bilateral_effusion:
        r_diaphragm_y -= 0.085
    r_diaphragm_mask = 1.0 / (1.0 + np.exp((ny - r_diaphragm_y) / 0.018))
    r_medial_mask = 1.0 / (1.0 + np.exp((nx + 0.065) / 0.018))
    right_lung = np.clip(1.0 - rl_dist ** 1.65, 0, 1) * r_diaphragm_mask * r_medial_mask

    ll_cx, ll_cy = 0.295, -0.02
    ll_rx = 0.240 * (1.0 + 0.23 * np.tanh((ny - ll_cy) * 1.85))
    ll_ry = 0.565
    ll_dist = ((nx - ll_cx) / np.clip(ll_rx, 0.08, 0.4)) ** 2 + ((ny - ll_cy) / ll_ry) ** 2
    l_diaphragm_y = 0.46 + 0.15 * ((nx - ll_cx) / 0.25) ** 2
    if bilateral_effusion:
        l_diaphragm_y -= 0.075
    l_diaphragm_mask = 1.0 / (1.0 + np.exp((ny - l_diaphragm_y) / 0.018))
    l_medial_mask = 1.0 / (1.0 + np.exp(-(nx - 0.065) / 0.018))
    left_lung = np.clip(1.0 - ll_dist ** 1.65, 0, 1) * l_diaphragm_mask * l_medial_mask

    lungs_combined = np.clip(right_lung + left_lung, 0, 1)
    img -= lungs_combined * 94.0

    # Subdiaphragmatic abdomen / liver dome / left hemidiaphragm density
    sub_r = (1.0 - r_diaphragm_mask) * (nx < 0.05) * edge_softness
    sub_l = (1.0 - l_diaphragm_mask) * (nx >= 0.05) * edge_softness
    img += (sub_r * 52.0 + sub_l * 46.0)

    # Gastric air bubble under left hemidiaphragm
    gastric_dist = ((nx - 0.24) / 0.075) ** 2 + ((ny - (l_diaphragm_y + 0.085)) / 0.048) ** 2
    img -= np.clip(1.0 - gastric_dist, 0, 1) * 30.0

    # Cardiac Silhouette & Aortic Knob
    heart_cx = 0.095 if not cardiomegaly else 0.130
    heart_cy = 0.185
    heart_rx = 0.190 if not cardiomegaly else 0.285
    heart_ry = 0.250 if not cardiomegaly else 0.290
    h_nx = (nx - heart_cx) * 0.94 - (ny - heart_cy) * 0.22
    h_ny = (nx - heart_cx) * 0.22 + (ny - heart_cy) * 0.94
    heart_dist = (h_nx / heart_rx) ** 2 + (h_ny / heart_ry) ** 2
    heart_profile = np.clip(1.0 - heart_dist ** 1.75, 0, 1) * l_diaphragm_mask
    img += heart_profile * 92.0

    # Aortic arch / knob
    aorta_dist = ((nx - 0.072) / 0.078) ** 2 + ((ny + 0.175) / 0.105) ** 2
    img += np.clip(1.0 - aorta_dist ** 1.5, 0, 1) * 48.0

    # Hilar vascular branching (radial vessels from bilateral hila)
    for side, h_x, h_y in [(-1, -0.11, -0.02), (1, 0.12, 0.00)]:
        dx = nx - h_x
        dy = ny - h_y
        rad = np.sqrt(dx ** 2 + dy ** 2) + 1e-4
        ang = np.arctan2(dy, dx * side)
        vessel_branches = (
            np.cos(ang * 7.0 + rad * 12.0) ** 4
            + 0.6 * np.sin(ang * 13.0 - rad * 18.0) ** 4
        )
        vessel_envelope = np.exp(-rad / 0.26) * (dx * side > -0.02)
        img += vessel_branches * vessel_envelope * lungs_combined * 25.0

    # Posterior & Anterior Thoracic Ribs (9 pairs of curved radiopaque arcs)
    rib_field = np.zeros_like(img)
    for i in range(9):
        rib_y0 = -0.48 + i * 0.104
        arc_curve = rib_y0 + 0.17 * (np.abs(nx) / 0.56) ** 1.85
        rib_band = np.exp(-((ny - arc_curve) / 0.016) ** 2)
        rib_lateral_env = np.clip((np.abs(nx) - 0.06) / 0.04, 0, 1) * np.clip(((0.58 - 0.02 * i) - np.abs(nx)) / 0.04, 0, 1)
        rib_field += rib_band * rib_lateral_env * (18.5 - i * 0.65)

        ant_curve = rib_y0 + 0.09 + 0.12 * (1.0 - (np.abs(nx) / 0.52) ** 1.5)
        ant_band = np.exp(-((ny - ant_curve) / 0.015) ** 2)
        rib_field += ant_band * rib_lateral_env * 8.0

    img += rib_field * (0.45 + 0.55 * lungs_combined)

    # Bilateral Clavicles
    for side in (-1, 1):
        clav_env = np.clip((nx * side - 0.04) / 0.03, 0, 1) * np.clip((0.64 - nx * side) / 0.05, 0, 1)
        clav_y = -0.49 - 0.145 * ((nx * side - 0.04) / 0.58) + 0.018 * np.sin((nx * side) * 10.0)
        clav_band = np.exp(-((ny - clav_y) / 0.021) ** 2) * clav_env
        img += clav_band * 44.0

    # Case-specific Pathological Findings
    if rll_opacity:
        op_dist = ((nx + 0.30) / 0.19) ** 2 + ((ny - 0.20) / 0.19) ** 2
        patch_noise = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (31, 31), 9)
        patch_noise = (patch_noise - patch_noise.min()) / (patch_noise.max() - patch_noise.min() + 1e-5)
        consolidation = np.clip(1.0 - op_dist ** 1.3, 0, 1) * (0.65 + 0.55 * patch_noise)
        bronch = np.exp(-(((ny - 0.18) - 0.75 * (nx + 0.24)) / 0.012) ** 2) * ((nx < -0.15) & (nx > -0.38))
        img += consolidation * right_lung * 68.0
        img -= bronch * consolidation * 18.0

    if bilateral_effusion:
        for side in (-1, 1):
            eff_y = 0.27 - 0.16 * ((np.abs(nx) - 0.28).clip(0, 0.35) / 0.25) ** 1.8
            eff_mask = (ny > eff_y) & (ny < 0.56) & (nx * side > 0.12) & (nx * side < 0.58)
            eff_grad = np.clip((ny - eff_y) / 0.14, 0, 1) * eff_mask
            img += eff_grad * 56.0
        hilar_haze = np.exp(-((nx / 0.34) ** 2 + (ny / 0.28) ** 2))
        img += hilar_haze * lungs_combined * 22.0

    if lul_opacity:
        lul_dist = ((nx - 0.27) / 0.16) ** 2 + ((ny + 0.24) / 0.17) ** 2
        tex = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (25, 25), 7)
        tex = (tex - tex.min()) / (tex.max() - tex.min() + 1e-5)
        lul_lesion = np.clip(1.0 - lul_dist ** 1.4, 0, 1) * (0.6 + 0.5 * tex)
        img += lul_lesion * left_lung * 62.0

    # Smooth anatomical boundaries and add subtle quantum mottle noise
    img = cv2.GaussianBlur(img, (7, 7), 1.8)
    quantum_noise = rng.normal(0, 2.0, (h, w)).astype(np.float32)
    img = np.clip(img + quantum_noise, 8, 246).astype(np.uint8)

    pil_img = Image.fromarray(img, mode="L")
    draw = ImageDraw.Draw(pil_img)
    draw.rectangle([36, 42, 74, 84], outline=215, width=2)
    draw.text((48, 52), "R", fill=225)
    draw.text((36, 92), "PA ERECT", fill=185)

    return pil_img


def ensure_sample_xrays(samples_dir="/home/user/static/samples", force=False):
    os.makedirs(samples_dir, exist_ok=True)
    samples = [
        {
            "filename": "cxr_normal_pa.png",
            "kwargs": dict(seed=101, cardiomegaly=False, rll_opacity=False, bilateral_effusion=False, lul_opacity=False),
        },
        {
            "filename": "cxr_rll_pneumonia.png",
            "kwargs": dict(seed=202, cardiomegaly=False, rll_opacity=True, bilateral_effusion=False, lul_opacity=False),
        },
        {
            "filename": "cxr_cardiomegaly_effusion.png",
            "kwargs": dict(seed=303, cardiomegaly=True, rll_opacity=False, bilateral_effusion=True, lul_opacity=False),
        },
        {
            "filename": "cxr_lul_infiltrate.png",
            "kwargs": dict(seed=404, cardiomegaly=False, rll_opacity=False, bilateral_effusion=False, lul_opacity=True),
        },
    ]
    created_paths = []
    for item in samples:
        out_path = os.path.join(samples_dir, item["filename"])
        if force or not os.path.exists(out_path):
            img = _create_base_thorax(size=800, **item["kwargs"])
            img.save(out_path, format="PNG")
        created_paths.append(out_path)
    return created_paths


if __name__ == "__main__":
    paths = ensure_sample_xrays(force=True)
    print("Regenerated sample radiographs:", paths)
