#!/usr/bin/env python3
"""Layer occupancy (LLM-3D Print): occupied pixels / total pixels in the region of interest.

  python occupancy.py top.jpg [--roi x0,y0,x1,y1] [--prev previous_top.jpg] [--mask-out m.png]

Occupied = material pixels, separated from the bed by Otsu thresholding on a background-normalised
grey image (works for light filament on a dark bed and vice versa; --invert forces polarity).
A drop in occupancy between consecutive top images at the same ROI flags missing extrusion; a rise
outside the expected footprint flags blobs/stringing. Use it as a number to support, not replace,
your visual judgement.
"""
import argparse
import json

import numpy as np
from PIL import Image, ImageFilter


def _otsu(g):
    h, _ = np.histogram(g, 256, (0, 256)); p = h / h.sum()
    w = np.cumsum(p); m = np.cumsum(p * np.arange(256)); mt = m[-1]
    s = (mt * w - m) ** 2 / (w * (1 - w) + 1e-12)
    return int(np.argmax(s))


def mask(path, roi=None, invert=None):
    im = Image.open(path).convert("L")
    if roi:
        im = im.crop(roi)
    bg = im.filter(ImageFilter.GaussianBlur(max(im.size) / 8))
    g = np.asarray(im, float) - np.asarray(bg, float)
    g = np.clip(g - g.min(), 0, None); g = (255 * g / (g.max() + 1e-9)).astype(np.uint8)
    t = _otsu(g)
    m = g > t
    if invert is None:  # material is the minority class unless told otherwise
        invert = m.mean() > 0.5
    return ~m if invert else m


def occupancy(path, roi=None, invert=None):
    m = mask(path, roi, invert)
    return {"occupancy": round(float(m.mean()), 4), "pixels": int(m.size)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image"); ap.add_argument("--roi"); ap.add_argument("--prev"); ap.add_argument("--mask-out")
    ap.add_argument("--invert", action="store_true", default=None)
    a = ap.parse_args()
    roi = tuple(int(v) for v in a.roi.split(",")) if a.roi else None
    r = occupancy(a.image, roi, a.invert)
    if a.prev:
        p = occupancy(a.prev, roi, a.invert)
        r["previous"] = p["occupancy"]; r["change"] = round(r["occupancy"] - p["occupancy"], 4)
    if a.mask_out:
        Image.fromarray((mask(a.image, roi, a.invert) * 255).astype(np.uint8)).save(a.mask_out)
    print(json.dumps(r))


if __name__ == "__main__":
    main()
