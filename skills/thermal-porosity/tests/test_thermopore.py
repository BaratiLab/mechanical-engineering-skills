"""Run: python tests/test_thermopore.py   (~1-2 min on CPU; deep-model smoke test skipped without torch)"""
import os, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import thermopore as T  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

check("IoU perfect", T.iou(np.eye(4) > 0, np.eye(4) > 0) == 1.0)
check("IoU half", abs(T.iou(np.array([1, 1, 0, 0]) > 0, np.array([1, 0, 0, 0]) > 0) - 0.5) < 1e-9)
check("IoU both empty = 1", T.iou(np.zeros(4) > 0, np.zeros(4) > 0) == 1.0)
stack = np.concatenate([np.full((30, 8, 8), 30.0), np.full((70, 8, 8), 30.0)])
stack[30:, 4, 4] = 2000
kept, thr = T.filter_frames(stack, n=20)
check("empty frames removed", kept.shape == (20, 8, 8) and kept[:, 4, 4].min() == 2000)

with tempfile.TemporaryDirectory() as d:
    run = os.path.join(d, "run")
    info = T.synth(run, steps=4, layers_per_step=8, frames=40, seed=1)
    check("synthetic shapes", info["frames_shape"] == [32, 40, 64, 64])
    count1, maps, thr, meta = T.labels(run, depth=1)
    count3, _, _, _ = T.labels(run, depth=3)
    check("deeper label window counts more pores", (count3 >= count1).all() and count3.sum() > count1.sum())
    _, _, thr_ms, _ = T.labels(run, esd_min="musigma")
    check("mu+sigma ESD threshold above zero", thr_ms > 20)
    tr, te = T.split(meta)
    steps = np.array(meta["step"])
    check("75/25 split within every step", all(te[steps == s].sum() == 2 for s in range(4)) and te.sum() == 8)
    F, _ = T.thermal_maps(np.load(os.path.join(run, "frames.npy")))
    check("thermal maps pooled to 16x16", F.shape == (32, 5, 16, 16))
    b = T.baseline(run, "localize")
    check(f"localization baseline beats predicting nothing (IoU {b['IoU_mean']})", b["IoU_mean"] > 0.05)
    c = T.baseline(run, "count")
    check("count baseline returns RMSE/R2", "RMSE" in c and "R2" in c and c["synthetic_data"])
    png = T.plot_layer(run, 5, os.path.join(d, "l5.png"))
    check("layer map written", os.path.getsize(png) > 10000)
    try:
        import torch  # noqa: F401
        r = T.train(run, "count", epochs=2, small=True)
        check("CNN trains (smoke)", "R2" in r)
        r = T.train(run, "localize", epochs=1, small=True)
        check("ViViT trains (smoke)", "IoU_mean" in r)
        CountCNN, ViViT = T.torch_models()
        m = ViViT(200, 64)   # paper size builds and runs
        out = m(torch.zeros(1, 200, 64, 64))
        check("paper-size ViViT outputs 16x16", tuple(out.shape) == (1, 16, 16))
    except ImportError:
        print("SKIP deep models (no torch)")
print(f"\n{ok} checks passed")
