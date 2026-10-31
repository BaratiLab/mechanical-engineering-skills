#!/usr/bin/env python3
"""Quick linear FEA on a STEP solid: gmsh (tet mesh) + scikit-fem (P2 elasticity).

Units: mm, N, MPa, tonne/mm^3 (steel rho = 7.85e-9). Frequencies in Hz.

Static:
  python fea.py part.step --E 205000 --nu 0.29 \
      --fix "x[0] < 1e-3" \
      --load "x[0] > 199.999" --force 0,0,-1000 --size 3 --out res
Modal:
  python fea.py part.step --E 205000 --nu 0.29 --rho 7.85e-9 \
      --fix "x[0] < 1e-3" --modes 6 --out res

--fix / --load are Python expressions on facet-midpoint coordinates x (shape 3xN),
evaluated with numpy as np. Use bounding-box planes from the CAD report.
--force is the TOTAL force vector spread uniformly over the load faces.
"""
import argparse
import json
import sys

import numpy as np


def mesh_step(path, size, order_hint=2):
    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.occ.importShapes(path)
    gmsh.model.occ.synchronize()
    gmsh.option.setNumber("Mesh.MeshSizeMax", size)
    gmsh.option.setNumber("Mesh.MeshSizeMin", size / 4)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 12)
    gmsh.model.mesh.generate(3)
    tags, coords, _ = gmsh.model.mesh.getNodes()
    p = coords.reshape(-1, 3).T
    idx = {t: i for i, t in enumerate(tags)}
    etypes, _, enodes = gmsh.model.mesh.getElements(3)
    t = None
    for et, en in zip(etypes, enodes):
        if et == 4:  # 4-node tet
            t = np.vectorize(idx.get)(en.reshape(-1, 4)).T
    gmsh.finalize()
    if t is None:
        sys.exit("meshing produced no tetrahedra")
    # drop unused nodes
    used = np.unique(t)
    remap = -np.ones(p.shape[1], dtype=int); remap[used] = np.arange(used.size)
    return p[:, used], remap[t]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step")
    ap.add_argument("--E", type=float, required=True)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--rho", type=float, default=7.85e-9)
    ap.add_argument("--fix", required=True)
    ap.add_argument("--load")
    ap.add_argument("--force", help="Fx,Fy,Fz total N")
    ap.add_argument("--modes", type=int, default=0)
    ap.add_argument("--size", type=float, default=5.0, help="max element size mm")
    ap.add_argument("--p1", action="store_true", help="linear tets (faster, stiffer)")
    ap.add_argument("--out", default="fea")
    a = ap.parse_args()

    from skfem import (Basis, BilinearForm, ElementTetP1, ElementTetP2, ElementVector,
                       FacetBasis, Functional, LinearForm, MeshTet, asm, condense, solve)
    from skfem.helpers import dot
    from skfem.models.elasticity import lame_parameters, linear_elasticity

    p, t = mesh_step(a.step, a.size)
    m = MeshTet(p, t)
    elem = ElementVector(ElementTetP1() if a.p1 else ElementTetP2())
    ib = Basis(m, elem)
    lam, mu = lame_parameters(a.E, a.nu)
    K = asm(linear_elasticity(lam, mu), ib)

    fix_fn = lambda x: eval(a.fix, {"np": np, "x": x})
    fixed_facets = m.facets_satisfying(fix_fn, boundaries_only=True)
    if fixed_facets.size == 0:
        sys.exit(f"--fix '{a.fix}' matched no boundary facets; check coordinates")
    D = ib.get_dofs(fixed_facets).all()
    res = {"mesh": {"nodes": int(m.p.shape[1]), "elements": int(m.t.shape[1]),
                    "element": "P1" if a.p1 else "P2", "size_mm": a.size, "dofs": int(ib.N)},
           "bc": {"fixed_facets": int(fixed_facets.size)}}

    if a.load and a.force:
        lf = m.facets_satisfying(lambda x: eval(a.load, {"np": np, "x": x}), boundaries_only=True)
        if lf.size == 0:
            sys.exit(f"--load '{a.load}' matched no boundary facets")
        fb = FacetBasis(m, elem, facets=lf)
        area = asm(Functional(lambda w: 1.0 + 0 * w.x[0]), fb)
        F = np.array([float(v) for v in a.force.split(",")])
        trac = F / area

        @LinearForm
        def lf_form(v, w):
            return trac[0] * v[0] + trac[1] * v[1] + trac[2] * v[2]

        f = asm(lf_form, fb)
        u = solve(*condense(K, f, D=D))
        ux, uy, uz = u[ib.nodal_dofs]
        umag = np.sqrt(ux ** 2 + uy ** 2 + uz ** 2)
        # stresses at quadrature points
        G = ib.interpolate(u).grad
        eps = 0.5 * (G + np.transpose(G, (1, 0, 2, 3)))
        tr = eps[0, 0] + eps[1, 1] + eps[2, 2]
        s = 2 * mu * eps
        for i in range(3):
            s[i, i] += lam * tr
        vm = np.sqrt(0.5 * ((s[0, 0] - s[1, 1]) ** 2 + (s[1, 1] - s[2, 2]) ** 2 + (s[2, 2] - s[0, 0]) ** 2)
                     + 3 * (s[0, 1] ** 2 + s[1, 2] ** 2 + s[0, 2] ** 2))
        vm_el = vm.max(axis=1)
        # reaction check
        Kfull_u = K @ u
        comp = [np.concatenate([ib.nodal_dofs[i]] + ([ib.edge_dofs[i]] if ib.edge_dofs.size else []))
                for i in range(3)]
        react = [float(Kfull_u[np.intersect1d(c, D)].sum()) for c in comp]
        applied = [float(f[c].sum()) for c in comp]
        res["static"] = {"load_area_mm2": float(area), "force_N": F.tolist(),
                         "max_disp_mm": float(umag.max()),
                         "max_disp_location": m.p[:, int(np.argmax(umag[:m.p.shape[1]]))].tolist(),
                         "max_von_mises_MPa": float(vm_el.max()),
                         "p99_von_mises_MPa": float(np.percentile(vm_el, 99)),
                         "max_vm_element_centroid": m.p[:, m.t[:, int(np.argmax(vm_el))]].mean(axis=1).tolist(),
                         "applied_sum_N": applied, "reaction_sum_N": react,
                         "equilibrium_error_pct": float(100 * np.linalg.norm(np.array(react) + F) / max(np.linalg.norm(F), 1e-12))}
        _plot(m, vm_el, umag[:m.p.shape[1]], a.out)
        res["files"] = [a.out + "_vm.png"]

    if a.modes:
        from skfem import solver_eigen_scipy_sym

        @BilinearForm
        def mass(u, v, w):
            return a.rho * dot(u, v)

        M = asm(mass, ib)
        lamb, _ = solve(*condense(K, M, D=D), solver=solver_eigen_scipy_sym(k=a.modes, sigma=0.0))
        res["modal"] = {"freq_Hz": (np.sqrt(np.abs(lamb)) / (2 * np.pi)).tolist()}

    with open(a.out + ".json", "w") as fh:
        json.dump(res, fh, indent=2)
    print(json.dumps(res, indent=2))


def _plot(m, vm_el, umag, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    c = m.p[:, m.t].mean(axis=1)
    fig = plt.figure(figsize=(11, 4.5))
    for k, (data, lab, pts) in enumerate(((vm_el, "von Mises (MPa)", c), (umag, "|u| (mm)", m.p))):
        ax = fig.add_subplot(1, 2, k + 1, projection="3d")
        sc = ax.scatter(*pts, c=data, cmap="turbo", s=2)
        fig.colorbar(sc, ax=ax, shrink=0.7, label=lab)
        ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_zlabel("z")
        rng = np.ptp(m.p, axis=1); ax.set_box_aspect(rng / rng.max())
    fig.tight_layout()
    fig.savefig(out + "_vm.png", dpi=150)


if __name__ == "__main__":
    main()
