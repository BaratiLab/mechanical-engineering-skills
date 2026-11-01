"""Run: python tests/test_sr.py   (~1 min CPU; model smoke tests skipped without torch)"""
import os, sys, tempfile, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import sr  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

rng = np.random.default_rng(0)
a = rng.random((64, 64)).astype(np.float32)
check("PSNR identical = 99", sr.psnr(a, a) == 99.0)
check("PSNR of 0.1 offset = 20 dB", abs(sr.psnr(a, a + 0.1) - 20) < 1e-3)
check("SSIM identical = 1", abs(sr.ssim(a, a) - 1) < 1e-9)
import cv2
blur = cv2.GaussianBlur(a, (0, 0), 2)
check("wavelet covariance distance: 0 for identical, larger for blurred", sr.cov_distance(a, a) < 1e-9 and sr.cov_distance(a, blur) > 0.2)

# roughness of a smooth disc << a jagged disc
yy, xx = np.mgrid[0:256, 0:256]
th = np.arctan2(yy - 128, xx - 128); rr = np.hypot(yy - 128, xx - 128)
smooth = rr < 80
jag = rr < 80 + 4 * np.sin(23 * th)
r1, r2 = sr.roughness([smooth], 10), sr.roughness([jag], 10)
check(f"roughness: jagged ({r2['Ra_um']}) >> smooth ({r1['Ra_um']}) um", r2["Ra_um"] > 3 * r1["Ra_um"] and r2["Ra_um"] > 10)

with tempfile.TemporaryDirectory() as d:
    plate = os.path.join(d, "plate")
    sr.synth(plate, layers=4, parts=9, hr=384)
    meta = json.load(open(os.path.join(plate, "meta.json")))
    r = sr.register(os.path.join(plate, "hr"), os.path.join(plate, "lr"), os.path.join(d, "al"))
    check(f"registration centre error < 1 px ({r['median_centre_error_px']})", r["median_centre_error_px"] < 1.0)
    hr = cv2.imread(os.path.join(plate, "hr", "layer_0001.png"), 0).astype(np.float32) / 255
    true = cv2.warpPerspective(hr, np.array(meta["true_homography_hr"]), hr.shape[::-1], borderMode=cv2.BORDER_REFLECT)
    reg = np.load(os.path.join(d, "al", "hr.npy"))[1].astype(np.float32)
    c = slice(40, -40)
    check("registered HR matches the true camera warp", np.abs(reg[c, c] - true[c, c]).mean() < 0.2 * np.abs(hr[c, c] - true[c, c]).mean())
    p = sr.patches(os.path.join(d, "al"), os.path.join(d, "pairs.npz"), per_layer=40)
    check("patch pairs with 20% test layers", p["pairs"] == 160 and p["test"] == 40)
    pp = sr.patches(os.path.join(d, "al"), os.path.join(d, "pairs_part.npz"), per_layer=40, split="part")
    check("part split holds out some patches", 0 < pp["test"] < pp["pairs"])
    dd = np.load(os.path.join(d, "pairs.npz"))
    m = sr.metrics(dd["hr"][:20], dd["lr"][:20])
    check("LR is measurably worse than HR on PSNR", m["HR|LR"]["PSNR_dB"][0] < 40)
    out, _ = sr.plate_compare(os.path.join(d, "al"), 10.0, layers=[0, 1])
    check("bicubic plate segments close to HR (IoU > 0.7)", out["LR_bicubic"]["part_IoU_vs_HR"] > 0.7)
    check("bicubic edges are smoother than HR edges", out["LR_bicubic"]["Ra_um"] < out["HR"]["Ra_um"])
    try:
        import torch  # noqa: F401
        for kind in ("cnn", "diffusion"):
            sr.train(os.path.join(d, "pairs.npz"), kind, os.path.join(d, f"{kind}.pt"), epochs=1, T=20, base=8)
            pr = sr.predict(os.path.join(d, f"{kind}.pt"), os.path.join(d, "pairs.npz"), os.path.join(d, f"{kind}_pred.npz"), steps=5, limit=8)
            q = np.load(os.path.join(d, f"{kind}_pred.npz"))
            check(f"{kind} trains and predicts in [0,1]", q["sr"].shape == (8, 64, 64) and q["sr"].min() >= 0 and q["sr"].max() <= 1)
    except ImportError:
        print("SKIP models (no torch)")
print(f"\n{ok} checks passed")
