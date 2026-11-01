"""Synthetic hand sketch (pen on paper): stadium outline with a round hole and a slot.
python make_sketch.py sketch.png"""
import sys
import cv2
import numpy as np
rng = np.random.default_rng(3)
img = np.full((600, 800), 255, np.uint8)
t = np.linspace(0, 2 * np.pi, 400)
wob = lambda n: rng.normal(0, 1.5, n).cumsum() * 0.15
pts = [(250 + 130 * np.cos(a), 300 + 130 * np.sin(a)) for a in np.linspace(np.pi / 2, 3 * np.pi / 2, 100)]
pts += [(550 + 130 * np.cos(a), 300 + 130 * np.sin(a)) for a in np.linspace(-np.pi / 2, np.pi / 2, 100)]
pts = np.array(pts); pts += np.c_[wob(len(pts)), wob(len(pts))]
cv2.polylines(img, [pts.astype(np.int32)], True, 30, 4)
hole = np.c_[250 + 55 * np.cos(t), 300 + 55 * np.sin(t)] + np.c_[wob(400), wob(400)]
cv2.polylines(img, [hole.astype(np.int32)], True, 30, 4)
slot = np.array([[470, 270], [640, 270], [640, 330], [470, 330]]) + rng.normal(0, 1.5, (4, 2))
cv2.polylines(img, [slot.astype(np.int32)], True, 30, 4)
img = cv2.GaussianBlur(img, (3, 3), 0)
img = np.clip(img.astype(int) + rng.normal(0, 6, img.shape), 0, 255).astype(np.uint8)
cv2.imwrite(sys.argv[1] if len(sys.argv) > 1 else "sketch.png", img)
