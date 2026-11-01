#!/usr/bin/env python3
"""GLU3D-style lattice unit-cell inverse design.

Implicit TPMS and hybrid TPMS unit cells -> voxels -> periodic homogenisation (6x6 C^H)
-> stiffness-conditioned 3D diffusion (DDPM) or parametric search -> watertight STL lattice.

Based on Jadhav et al., "Generative Lattice Units with 3D Diffusion for Inverse Design: GLU3D",
Adv. Funct. Mater. 34 (2024) 2404165.

Geometry, homogenisation, metrics, search and STL export need numpy + scipy
(+ scikit-image and trimesh for meshes, pyamg optional for speed). The diffusion
model and surrogate need PyTorch.
"""
import argparse, json, math, os, sys, time
import numpy as np

# ----------------------------------------------------------------------------------------------
# 1. Implicit geometry
# ----------------------------------------------------------------------------------------------
# Nodal (trigonometric) approximations, X = 2*pi*x/L. Every term is a product of cos/sin of
# integer multiples, so every family and every blend of families is periodic on the unit cell.
c, s = np.cos, np.sin
FAMILIES = {
    "primitive":   lambda X, Y, Z: c(X) + c(Y) + c(Z),
    "gyroid":      lambda X, Y, Z: s(X)*c(Y) + s(Y)*c(Z) + s(Z)*c(X),
    "diamond":     lambda X, Y, Z: (s(X)*s(Y)*s(Z) + s(X)*c(Y)*c(Z) + c(X)*s(Y)*c(Z)
                                    + c(X)*c(Y)*s(Z)),
    "neovius":     lambda X, Y, Z: 3*(c(X) + c(Y) + c(Z)) + 4*c(X)*c(Y)*c(Z),
    "iwp":         lambda X, Y, Z: (2*(c(X)*c(Y) + c(Y)*c(Z) + c(Z)*c(X))
                                    - (c(2*X) + c(2*Y) + c(2*Z))),
    "fischer_koch_s": lambda X, Y, Z: (c(2*X)*s(Y)*c(Z) + c(2*Y)*s(Z)*c(X)
                                       + c(2*Z)*s(X)*c(Y)),
    "frd":         lambda X, Y, Z: (4*c(X)*c(Y)*c(Z)
                                    - (c(2*X)*c(2*Y) + c(2*Y)*c(2*Z) + c(2*Z)*c(2*X))),
    "lidinoid":    lambda X, Y, Z: (0.5*(s(2*X)*c(Y)*s(Z) + s(2*Y)*c(Z)*s(X) + s(2*Z)*c(X)*s(Y))
                                    - 0.5*(c(2*X)*c(2*Y) + c(2*Y)*c(2*Z) + c(2*Z)*c(2*X)) + 0.15),
    "split_p":     lambda X, Y, Z: (1.1*(s(2*X)*s(Z)*c(Y) + s(2*Y)*s(X)*c(Z) + s(2*Z)*s(Y)*c(X))
                                    - 0.2*(c(2*X)*c(2*Y) + c(2*Y)*c(2*Z) + c(2*Z)*c(2*X))
                                    - 0.4*(c(2*X) + c(2*Y) + c(2*Z))),
    "pw_hybrid":   lambda X, Y, Z: (4*(c(X)*c(Y) + c(Y)*c(Z) + c(Z)*c(X))
                                    - 3*c(X)*c(Y)*c(Z) + 2.4),
    "double_primitive": lambda X, Y, Z: (0.5*(c(X)*c(Y) + c(Y)*c(Z) + c(Z)*c(X))
                                         + 0.2*(c(2*X) + c(2*Y) + c(2*Z))),
    "double_diamond": lambda X, Y, Z: (s(X)*s(Y) + s(Y)*s(Z) + s(X)*s(Z) + c(X)*c(Y)*c(Z)),
}
_NORM = {}


def grid(res):
    """Node-sampled grid over one period including both faces, as in the paper (64^3)."""
    t = np.linspace(0, 2*np.pi, res)
    return np.meshgrid(t, t, t, indexing="ij")


def family_field(name, res, freq=(1, 1, 1)):
    """Family surface function, normalised to max |F| = 1 so h and a mean the same for all."""
    X, Y, Z = grid(res)
    F = FAMILIES[name](freq[0]*X, freq[1]*Y, freq[2]*Z)
    if name not in _NORM:
        Xn, Yn, Zn = grid(48)
        _NORM[name] = float(np.abs(FAMILIES[name](Xn, Yn, Zn)).max())
    return F / _NORM[name]


def sigmoid(t):
    return 1.0 / (1.0 + math.exp(-t))


def hybrid(phis, mode, t):
    """Transition functions, Eqs. (3)-(7) of the paper (t is a constant)."""
    p = phis
    if mode == "H2":
        return sigmoid(t)*p[0] + (1 - sigmoid(t))*p[1]
    if mode == "H2t":
        return t*p[0]*math.cos(t) + (1 - t)*p[1]*math.sin(t)
    if mode == "H3":
        w = sigmoid(t)
        return w*p[0] + w*math.cos(2*math.pi*t)*p[1] + (1 - (w + w*math.cos(2*math.pi*t)))*p[2]
    if mode == "H3t":
        return t*p[0]*math.cos(t) + (1 - t)/2*p[1]*math.sin(t) + (1 - t)/2*math.tan(t)*p[2]
    if mode == "H4":   # Eq. (7) exactly as printed (the last two terms multiply)
        return t*p[0]*math.cos(t) + t*p[1]*math.sin(t) + t*math.tan(t)*p[2]*t*p[3]
    raise ValueError(mode)


NPHI = {"single": 1, "H2": 2, "H2t": 2, "H3": 3, "H3t": 3, "H4": 4}


STRUTS = {"sc": [(1, 0, 0), (0, 1, 0), (0, 0, 1)],
          "bcc": [(1, 1, 1), (-1, 1, 1), (1, -1, 1), (1, 1, -1)],
          "fcc": [(0, 1, 1), (0, 1, -1), (1, 0, 1), (1, 0, -1), (1, 1, 0), (1, -1, 0)]}


def strut_field(kind, r, res):
    """Reference strut lattices (the paper compares against simple cubic and BCC):
    distance to the periodic strut lines minus the strut radius r (cell size 1)."""
    t = np.linspace(0, 1, res)
    P = np.stack(np.meshgrid(t, t, t, indexing="ij"), -1)
    d = np.full(P.shape[:3], np.inf)
    origin = np.full(3, 0.5) if kind == "bcc" else np.zeros(3)
    for u in STRUTS[kind]:
        u = np.asarray(u, float); u /= np.linalg.norm(u)
        for sh in np.array(np.meshgrid([-1, 0, 1], [-1, 0, 1], [-1, 0, 1])).reshape(3, -1).T:
            q = P - (origin + sh)
            perp = q - (q @ u)[..., None] * u
            d = np.minimum(d, np.linalg.norm(perp, axis=-1))
    return d - r


def cell_field(spec, res):
    """spec = {families:[...], mode, t, h, a, kind:'sheet'|'network'|'strut'} -> implicit field.
    Solid where field < 0. Sheet (paper): phi^2 - h^2 with phi = F + a. Network: F + a.
    Strut: families=['sc'|'bcc'|'fcc'], h = strut radius as a fraction of the cell."""
    if spec.get("kind") == "strut":
        return strut_field(spec["families"][0], spec["h"], res)
    fams = spec["families"]
    mode = spec.get("mode", "single")
    freq = tuple(spec.get("freq", (1, 1, 1)))     # integer periods per axis (Eqs. 1-2: s_x, s_y, s_z)
    phis = [family_field(f, res, freq) for f in fams]
    F = phis[0] if mode == "single" else hybrid(phis, mode, spec.get("t", 0.0))
    if mode != "single":                     # keep h and a on the same scale as the families
        F = F / max(np.abs(F).max(), 1e-9)
    phi = F + spec.get("a", 0.0)
    if spec.get("kind", "sheet") == "network":
        return phi
    return phi**2 - spec.get("h", 0.2)**2


def voxels(field):
    """Binary voxels on the node grid (1 = material)."""
    return (field < 0).astype(np.uint8)


def periodic_voxels(field, res=None):
    """Periodic voxel grid for homogenisation: drop the duplicated last face (optionally resample)."""
    if res is not None and res + 1 != field.shape[0]:
        from scipy.ndimage import zoom
        field = zoom(field, (res + 1) / field.shape[0], order=1)
    return voxels(field)[:-1, :-1, :-1]


# ----------------------------------------------------------------------------------------------
# 2. Manufacturability filters (paper: >2 surfaces or non-manifold rejected; Dice > 0.75 rejected)
# ----------------------------------------------------------------------------------------------
def periodic_components(mask):
    """Number of connected components under periodic wrap (6-connectivity) and the label array."""
    from scipy.ndimage import label
    lab, n = label(mask)
    if n == 0:
        return 0, lab
    parent = list(range(n + 1))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for ax in range(3):
        a = np.take(lab, 0, axis=ax).ravel()
        b = np.take(lab, -1, axis=ax).ravel()
        for u, v in zip(a[(a > 0) & (b > 0)], b[(a > 0) & (b > 0)]):
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
    roots = np.array([find(i) for i in range(n + 1)])
    lab = roots[lab]
    lab[mask == 0] = 0
    return len(set(roots[1:])), lab


def keep_largest(mask):
    n, lab = periodic_components(mask)
    if n <= 1:
        return mask, n
    ids, cnt = np.unique(lab[lab > 0], return_counts=True)
    return (lab == ids[np.argmax(cnt)]).astype(np.uint8), n


def printable(field, vmin=0.05, vmax=0.95):
    """Checks used for the dataset. Returns (ok, info)."""
    pv = voxels(field)[:-1, :-1, :-1]
    vf = float(pv.mean())
    info = {"vfrac": vf}
    if not (vmin < vf < vmax):
        return False, {**info, "reason": "volume fraction"}
    ns, ls = periodic_components(pv)
    nv, lv = periodic_components(1 - pv)
    info.update(solid_parts=ns, void_parts=nv)
    if ns != 1:
        return False, {**info, "reason": "solid not one connected piece"}
    if not spans(ls, ls.max()):
        return False, {**info, "reason": "solid does not reach every face (lattice falls apart)"}
    # every void region must reach the cell faces, otherwise it is a sealed cavity that traps
    # powder/resin (sheet TPMS have two interpenetrating, open labyrinths)
    if any(not spans(lv, i) for i in np.unique(lv[lv > 0])):
        return False, {**info, "reason": "closed internal cavities (unremovable powder/resin)"}
    return True, info


def spans(lab, i):
    return all((np.take(lab, 0, ax) == i).any() and (np.take(lab, -1, ax) == i).any()
               for ax in range(3))


def dice(a, b):
    a = a.astype(bool); b = b.astype(bool)
    return 2.0 * (a & b).sum() / max(a.sum() + b.sum(), 1)


# ----------------------------------------------------------------------------------------------
# 3. Periodic voxel homogenisation (energy-based, as Dong et al. 2019 used in the paper)
# ----------------------------------------------------------------------------------------------
def iso_D(E=1.0, nu=0.3):
    lam = E*nu/((1+nu)*(1-2*nu)); mu = E/(2*(1+nu))
    D = np.zeros((6, 6))
    D[:3, :3] = lam
    D[np.arange(3), np.arange(3)] = lam + 2*mu
    D[3, 3] = D[4, 4] = D[5, 5] = mu
    return D


_LOCAL = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                   [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]])


def hex8(h, nu):
    """Unit-modulus element stiffness ke (24x24), load fe (24x6) and volume for a cube of side h.
    Voigt order [xx, yy, zz, yz, xz, xy], engineering shear strain."""
    D = iso_D(1.0, nu)
    g = np.array([-1, 1]) / math.sqrt(3)
    ke = np.zeros((24, 24)); fe = np.zeros((24, 6))
    sgn = 2*_LOCAL - 1
    for xi in g:
        for eta in g:
            for zeta in g:
                dN = np.zeros((8, 3))
                for a in range(8):
                    sx, sy, sz = sgn[a]
                    dN[a] = [sx*(1+sy*eta)*(1+sz*zeta), sy*(1+sx*xi)*(1+sz*zeta),
                             sz*(1+sx*xi)*(1+sy*eta)]
                dN *= 0.125 * (2.0/h)        # d/dx = (2/h) d/dxi
                B = np.zeros((6, 24))
                for a in range(8):
                    dx, dy, dz = dN[a]
                    B[0, 3*a] = dx; B[1, 3*a+1] = dy; B[2, 3*a+2] = dz
                    B[3, 3*a+1] = dz; B[3, 3*a+2] = dy
                    B[4, 3*a] = dz;   B[4, 3*a+2] = dx
                    B[5, 3*a] = dy;   B[5, 3*a+1] = dx
                w = (h/2)**3
                ke += B.T @ D @ B * w
                fe += B.T @ D * w
    return ke, fe, h**3, D


def homogenize(Emat, nu=0.3, tol=1e-8, verbose=False):
    """Emat: (n,n,n) Young's modulus per voxel (0 = void) of ONE periodic cell of side 1.
    Returns the 6x6 homogenised stiffness C^H. Disconnected material must be removed first."""
    import scipy.sparse as sp
    n = Emat.shape[0]
    assert Emat.shape == (n, n, n)
    h = 1.0 / n
    ke, fe, Ve, Dhat = hex8(h, nu)
    solid = np.argwhere(Emat > 0)
    Ee = Emat[Emat > 0].astype(float)
    if len(Ee) == 0:
        return np.zeros((6, 6))
    nodes = (solid[:, None, :] + _LOCAL[None]) % n                 # (ne, 8, 3)
    gid = nodes[..., 0] + n*nodes[..., 1] + n*n*nodes[..., 2]      # periodic node ids
    used, inv = np.unique(gid, return_inverse=True)
    inv = inv.reshape(gid.shape)
    edof = (3*inv[..., None] + np.arange(3)).reshape(len(Ee), 24).astype(np.int64)
    ndof = 3*len(used)
    rows = np.repeat(edof, 24, axis=1).ravel()
    cols = np.tile(edof, (1, 24)).ravel()
    vals = (Ee[:, None] * ke.ravel()[None]).ravel()
    K = sp.coo_matrix((vals, (rows, cols)), shape=(ndof, ndof)).tocsr()
    F = np.zeros((ndof, 6))
    np.add.at(F, edof.ravel(), (Ee[:, None, None] * fe[None]).reshape(-1, 6))
    free = np.arange(3, ndof)                    # pin one node (removes rigid translation)
    Kf = K[free][:, free]
    U = np.zeros((ndof, 6))
    t0 = time.time()
    try:
        import pyamg
        B = np.kron(np.ones((len(free) // 3, 1)), np.eye(3))   # near-null space: translations
        ml = pyamg.smoothed_aggregation_solver(Kf.tocsr(), B=B,
                                               symmetry="symmetric")
        for j in range(6):
            U[free, j] = ml.solve(F[free, j], tol=tol, accel="cg", maxiter=500)
    except ImportError:
        from scipy.sparse.linalg import spsolve
        U[free] = spsolve(Kf.tocsc(), F[free]).reshape(-1, 6)
    if verbose:
        print(f"  homogenised {n}^3 ({len(Ee)} solid voxels, {ndof} dof) in {time.time()-t0:.1f}s",
              file=sys.stderr)
    X = U[edof]                                   # (ne, 24, 6)
    C = (Ee.sum() * Ve) * Dhat
    feX = np.einsum("aj,eai->eij", fe, X)        # fe^T X per element, (ne, 6, 6)
    XkX = np.einsum("eai,ab,ebj->eij", X, ke, X)
    C = C + np.einsum("e,eij->ij", Ee, -feX - feX.transpose(0, 2, 1) + XkX)
    return 0.5 * (C + C.T)


def constants(C):
    """Engineering constants from C (Voigt xx,yy,zz,yz,xz,xy)."""
    S = np.linalg.inv(C)
    out = {"E1": 1/S[0, 0], "E2": 1/S[1, 1], "E3": 1/S[2, 2],
           "G23": 1/S[3, 3], "G13": 1/S[4, 4], "G12": 1/S[5, 5],
           "nu12": -S[0, 1]/S[0, 0], "nu13": -S[0, 2]/S[0, 0], "nu23": -S[1, 2]/S[1, 1]}
    denom = C[0, 0] - C[0, 1]
    out["zener"] = 2*C[3, 3]/denom if abs(denom) > 1e-12 else float("nan")
    e = np.array([out["E1"], out["E2"], out["E3"]])
    out["E_spread"] = float((e.max() - e.min()) / e.mean())
    ed = directional_E(S)
    out["E_dir_min"], out["E_dir_max"] = float(ed.min()), float(ed.max())
    return {k: float(v) for k, v in out.items()}


def _sphere(n=600):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2*i/n); th = np.pi*(1 + 5**0.5)*i
    return np.stack([np.cos(th)*np.sin(phi), np.sin(th)*np.sin(phi), np.cos(phi)], 1)


def directional_E(S, dirs=None):
    """Young's modulus along each direction d: 1/E = sigma^T S sigma, sigma = Voigt(d d^T)."""
    d = _sphere() if dirs is None else np.asarray(dirs, float)
    sig = np.stack([d[:, 0]**2, d[:, 1]**2, d[:, 2]**2, d[:, 1]*d[:, 2], d[:, 0]*d[:, 2],
                    d[:, 0]*d[:, 1]], 1)
    return 1.0 / np.einsum("ni,ij,nj->n", sig, S, sig)


def target_C(E, G=None, nu=0.3):
    """Orthotropic stiffness from target constants. E: scalar or (E1,E2,E3); G: scalar or 3-tuple."""
    E = np.broadcast_to(np.asarray(E, float), (3,))
    if G is None:
        G = E.mean() / (2*(1+nu))
    G = np.broadcast_to(np.asarray(G, float), (3,))
    S = np.zeros((6, 6))
    for i in range(3):
        S[i, i] = 1/E[i]
    for i, j in [(0, 1), (0, 2), (1, 2)]:
        S[i, j] = S[j, i] = -nu/E[i]
    S[3, 3], S[4, 4], S[5, 5] = 1/G[0], 1/G[1], 1/G[2]
    return np.linalg.inv(0.5*(S + S.T))


def cell_stiffness(field, Es=1.0, nu=0.3, hres=32, verbose=False):
    """Field -> (C^H, constants, vfrac). Stray islands are removed first (they break the FEM)."""
    full = periodic_voxels(field)
    pv = periodic_voxels(field, hres if field.shape[0] - 1 > hres else None)
    kept, nparts = keep_largest(pv)
    if abs(kept.mean() - full.mean()) > 0.1 * max(full.mean(), 1e-9):
        # thin walls lost or broken when coarsening: homogenise at full resolution
        kept, nparts = keep_largest(full)
    pv = kept
    if pv.mean() < 0.01:
        return np.zeros((6, 6)), {}, float(pv.mean()), nparts
    C = homogenize(pv * Es, nu, verbose=verbose)
    ev = np.linalg.eigvalsh(C)
    ok = ev.min() > 1e-6 * ev.max()       # positive definite = the cell carries load in all modes
    if not ok and pv.shape[0] < full.shape[0]:
        return cell_stiffness(field, Es, nu, hres=field.shape[0], verbose=verbose)
    return C, (constants(C) if ok else {}), float(pv.mean()), nparts


# ----------------------------------------------------------------------------------------------
# 4. Tanh scaling (Eq. 9) for the diffusion model
# ----------------------------------------------------------------------------------------------
def tanh_scale(field, phi_hat_min=0.75):
    """alpha = atanh(phi_hat_min)/|min phi|; phi_s = tanh(alpha*phi). Zero level set preserved,
    the most negative (inside) value maps to -phi_hat_min, the outside saturates towards +1.
    phi_hat_min=None reproduces the naive tanh(phi) the paper compares against."""
    if phi_hat_min is None:
        return np.tanh(field)
    m = abs(min(float(field.min()), -1e-6))
    return np.tanh(field * math.atanh(phi_hat_min) / m)


# ----------------------------------------------------------------------------------------------
# 5. Evaluation metrics (Eqs. 12-17)
# ----------------------------------------------------------------------------------------------
def periodicity(field):
    """Sum over the 3 opposite-face pairs of the MAE between binary face voxels (0 = periodic)."""
    v = voxels(field).astype(float)
    return float(sum(np.abs(np.take(v, 0, ax) - np.take(v, -1, ax)).mean() for ax in range(3)))


def mesh(field, cell_mm=1.0, tiles=(1, 1, 1)):
    """Watertight triangle mesh of the solid (field < 0), tiled; padded so the boundary is capped."""
    from skimage.measure import marching_cubes
    base = field[:-1, :-1, :-1]
    f = np.tile(base, tiles)
    f = np.concatenate([f, f[:1]], 0); f = np.concatenate([f, f[:, :1]], 1)
    f = np.concatenate([f, f[:, :, :1]], 2)
    f = np.pad(f, 1, constant_values=max(1.0, float(f.max())))
    if not (f.min() < 0 < f.max()):
        return None
    step = cell_mm / (field.shape[0] - 1)
    verts, faces, _, _ = marching_cubes(f, 0.0, spacing=(step, step, step))
    verts -= step
    return verts, faces


def save_stl(verts, faces, path):
    import trimesh
    m = trimesh.Trimesh(verts, faces[:, ::-1], process=True)
    trimesh.repair.fix_normals(m)
    m.export(path)
    return m


def surface_points(field, npts=2000, seed=0):
    import trimesh
    mm = mesh(field)
    if mm is None:
        return None
    m = trimesh.Trimesh(*mm, process=False)
    pts, _ = trimesh.sample.sample_surface(m, npts, seed=seed)
    return np.asarray(pts)


def chamfer_hausdorff(A, B):
    from scipy.spatial import cKDTree
    da = cKDTree(B).query(A)[0]; db = cKDTree(A).query(B)[0]
    return 0.5*da.mean() + 0.5*db.mean(), 0.5*da.max() + 0.5*db.max()


def diversity(gen_fields, train_fields, npts=2000):
    """Paper Eq. (17): for each generated cell, best Dice / Chamfer / Hausdorff vs the training set."""
    tv = [voxels(f) for f in train_fields]
    tp = [surface_points(f, npts) for f in train_fields]
    D, Cd, H = [], [], []
    for g in gen_fields:
        gv = voxels(g); gp = surface_points(g, npts)
        D.append(max(dice(gv, t) for t in tv))
        if gp is not None:
            ch = [chamfer_hausdorff(gp, t) for t in tp if t is not None]
            Cd.append(min(x[0] for x in ch)); H.append(min(x[1] for x in ch))
    return {"dice_max_mean": float(np.mean(D)), "chamfer_min_mean": float(np.mean(Cd)),
            "hausdorff_min_mean": float(np.mean(H))}


def success(field):
    """Paper's generation success: vfrac > 0.05 and a closed mesh exists at level set 0."""
    return bool(voxels(field).mean() > 0.05 and field.min() < 0 < field.max())


# ----------------------------------------------------------------------------------------------
# 6. Dataset generation
# ----------------------------------------------------------------------------------------------
def random_spec(rng, kinds=("sheet",)):
    fams = list(FAMILIES)
    if rng.random() < 0.4:
        spec = {"families": [str(rng.choice(fams))], "mode": "single"}
    else:
        mode = str(rng.choice(["H2", "H2t", "H3", "H3t"]))
        spec = {"families": [str(x) for x in rng.choice(fams, NPHI[mode], replace=False)],
                "mode": mode, "t": float(rng.uniform(-3, 3) if mode == "H2" else rng.uniform(0.05, 0.95))}
    if rng.random() < 0.35:                          # anisotropy: 2 periods along one or two axes
        fr = [1, 1, 1]
        for ax in rng.choice(3, int(rng.integers(1, 3)), replace=False):
            fr[ax] = 2
        spec["freq"] = fr
    spec["kind"] = str(rng.choice(list(kinds)))
    spec["a"] = float(rng.uniform(-0.3, 0.3))
    spec["h"] = float(rng.uniform(0.08, 0.5)) if spec["kind"] == "sheet" else 0.0
    return spec


def make_dataset(n, res, out, seed=0, kinds=("sheet",), Es=1.0, nu=0.3, hres=32,
                 dice_max=0.75, max_tries=None):
    rng = np.random.default_rng(seed)
    fields, Cs, specs, vf, rejected = [], [], [], [], {}
    tries = 0
    max_tries = max_tries or 30*n
    t0 = time.time()
    while len(fields) < n and tries < max_tries:
        tries += 1
        spec = random_spec(rng, kinds)
        f = cell_field(spec, res)
        ok, info = printable(f)
        if not ok:
            rejected[info["reason"]] = rejected.get(info["reason"], 0) + 1
            continue
        v = voxels(f)
        if any(dice(v, voxels(g)) > dice_max for g in fields[-400:]):
            rejected["too similar (Dice > %.2f)" % dice_max] = rejected.get("too similar (Dice > %.2f)" % dice_max, 0) + 1
            continue
        C, k, vfrac, _ = cell_stiffness(f, Es, nu, hres)
        if not k:
            rejected["homogenisation failed"] = rejected.get("homogenisation failed", 0) + 1
            continue
        fields.append(f.astype(np.float32)); Cs.append(C); specs.append(spec); vf.append(vfrac)
        if len(fields) % 10 == 0:
            print(f"  {len(fields)}/{n} accepted ({tries} tried, {time.time()-t0:.0f}s)", file=sys.stderr)
    np.savez_compressed(out, fields=np.array(fields), C=np.array(Cs), vfrac=np.array(vf),
                        specs=json.dumps(specs), res=res, Es=Es, nu=nu)
    return {"accepted": len(fields), "tried": tries, "rejected": rejected, "out": out}


def load_dataset(path):
    d = np.load(path, allow_pickle=False)
    return {"fields": d["fields"], "C": d["C"], "vfrac": d["vfrac"],
            "specs": json.loads(str(d["specs"])), "res": int(d["res"]),
            "Es": float(d["Es"]), "nu": float(d["nu"])}


def C_all_constants(Cs):
    return [constants(C) for C in Cs]


# ----------------------------------------------------------------------------------------------
# 7. Parametric inverse design by search (no GPU needed)
# ----------------------------------------------------------------------------------------------
KEYS = ["E1", "E2", "E3", "G23", "G13", "G12"]


def target_error(k, target, weights=None):
    """Mean |log| error over the target constants that are given."""
    errs = [abs(math.log(max(k[key], 1e-12) / v)) for key, v in target.items() if key in k]
    return float(np.mean(errs)) if errs else float("inf")


def search(target, data=None, res=33, hres=24, budget=40, seed=0, Es=1.0, nu=0.3,
           kinds=("sheet",), density_weight=0.0, verbose=True):
    """Find printable cells whose homogenised constants match `target` (dict, relative to Es).
    1) rank dataset cells (if given) or random specs by error, 2) refine h and a locally."""
    rng = np.random.default_rng(seed)
    cand = []
    if data is not None:
        ds = load_dataset(data)
        ks = C_all_constants(ds["C"])
        for spec, k, v in zip(ds["specs"], ks, ds["vfrac"]):
            cand.append((target_error(k, target) + density_weight*v, spec, k, float(v)))
    else:
        for _ in range(budget):
            spec = random_spec(rng, kinds)
            f = cell_field(spec, res)
            if not printable(f)[0]:
                continue
            _, k, v, _ = cell_stiffness(f, Es, nu, hres)
            if k:
                cand.append((target_error(k, target) + density_weight*v, spec, k, v))
    cand.sort(key=lambda x: x[0])
    best = list(cand[:3])
    evals = 0
    for score, spec, k, v in list(cand[:3]):
        step_h, step_a = 0.06, 0.08
        cur = (score, spec, k, v)
        for it in range(max(2, budget // 6)):
            trial = dict(cur[1])
            if trial.get("kind", "sheet") == "sheet":
                trial["h"] = float(np.clip(trial["h"] + rng.normal(0, step_h), 0.04, 0.7))
            trial["a"] = float(np.clip(trial["a"] + rng.normal(0, step_a), -0.6, 0.6))
            f = cell_field(trial, res)
            evals += 1
            if not printable(f)[0]:
                continue
            _, kt, vt, _ = cell_stiffness(f, Es, nu, hres)
            if not kt:
                continue
            st = target_error(kt, target) + density_weight*vt
            if st < cur[0]:
                cur = (st, trial, kt, vt)
            else:
                step_h *= 0.8; step_a *= 0.8
        best.append(cur)
    best.sort(key=lambda x: x[0])
    seen, out = set(), []
    for sc, spec, k, v in best:
        key = json.dumps(spec, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append({"score_log_err": round(sc, 4), "spec": spec, "vfrac": round(v, 4),
                    "constants": {kk: round(k[kk], 5) for kk in KEYS + ["zener"]}})
    return out[:5]


# ----------------------------------------------------------------------------------------------
# 8. Diffusion model and surrogate (PyTorch)
# ----------------------------------------------------------------------------------------------
def tri(C):
    i, j = np.triu_indices(6)
    return np.asarray(C)[..., i, j]


def cond_vectors(C, vfrac, stats=None, with_vfrac=True):
    """Paper: every stiffness entry standardised to mean 50, std 1 (keeps it far from the
    all-zero 'unconditional' vector). Upper triangle (21 entries) + optionally volume fraction."""
    x = tri(C)
    if with_vfrac:
        x = np.concatenate([x, np.asarray(vfrac)[..., None]], -1)
    if stats is None:
        stats = {"mu": x.mean(0).tolist(), "sd": (x.std(0) + 1e-9).tolist()}
    return (x - np.array(stats["mu"])) / np.array(stats["sd"]) + 50.0, stats


def torch_parts():
    import torch, torch.nn as nn, torch.nn.functional as Fn

    class Res(nn.Module):
        def __init__(s, ci, co, ed):
            super().__init__()
            s.n1 = nn.GroupNorm(min(4, ci), ci); s.c1 = nn.Conv3d(ci, co, 3, padding=1, padding_mode="circular")
            s.e = nn.Linear(ed, co)
            s.n2 = nn.GroupNorm(min(4, co), co); s.c2 = nn.Conv3d(co, co, 3, padding=1, padding_mode="circular")
            s.sk = nn.Conv3d(ci, co, 1) if ci != co else nn.Identity()

        def forward(s, x, e):
            h = s.c1(Fn.silu(s.n1(x))) + s.e(e)[:, :, None, None, None]
            return s.c2(Fn.silu(s.n2(h))) + s.sk(x)

    class UNet3D(nn.Module):
        """3D conditional U-Net with ResNet blocks; channels like the paper's '148163264'."""
        def __init__(s, chans=(1, 4, 8, 16, 32), cond_dim=22, T=500, ed=64):
            super().__init__()
            # time step: sinusoidal features -> learnable MLP. (A free nn.Embedding table per step,
            # read literally from the paper, sees each of the 500 steps too rarely on small data.)
            s.ed = ed
            s.temb = nn.Sequential(nn.Linear(ed, ed), nn.SiLU(), nn.Linear(ed, ed))
            s.cenc = nn.Linear(cond_dim, ed)              # linear encoder for the stiffness
            s.mlp = nn.Sequential(nn.SiLU(), nn.Linear(ed, ed))
            s.inc = nn.Conv3d(1, chans[1], 3, padding=1, padding_mode="circular")
            s.down = nn.ModuleList(); s.up = nn.ModuleList()
            cs = list(chans[1:])
            for a, b in zip(cs[:-1], cs[1:]):
                s.down.append(Res(a, b, ed))
            s.mid = Res(cs[-1], cs[-1], ed)
            for a, b in zip(cs[::-1][:-1], cs[::-1][1:]):
                s.up.append(Res(a + b, b, ed))
            s.out = nn.Conv3d(cs[0], 1, 1)

        def forward(s, x, t, cvec):
            # entries are ~50 (null = 0); /50 keeps the encoder output O(1) at initialisation
            # without changing the separation between conditioned and unconditional inputs
            half = s.ed // 2
            fr = torch.exp(-math.log(10000.0) * torch.arange(half, device=x.device) / half)
            ang = t.float()[:, None] * fr[None]
            e = s.mlp(s.temb(torch.cat([ang.sin(), ang.cos()], 1)) + s.cenc(cvec / 50.0))
            h = s.inc(x); skips = []
            for blk in s.down:
                skips.append(h)
                h = blk(h, e)
                h = Fn.avg_pool3d(h, 2)
            h = s.mid(h, e)
            for blk in s.up:
                h = Fn.interpolate(h, scale_factor=2, mode="nearest")
                h = blk(torch.cat([h, skips.pop()], 1), e)
            return s.out(h)

    class Surrogate(nn.Module):
        """Small 3D CNN: implicit field -> log10 of (E1,E2,E3,G23,G13,G12)/Es."""
        def __init__(s, nout=6):
            super().__init__()
            s.f = nn.Sequential(nn.Conv3d(1, 8, 3, padding=1, padding_mode="circular"), nn.SiLU(), nn.AvgPool3d(2),
                                nn.Conv3d(8, 16, 3, padding=1, padding_mode="circular"), nn.SiLU(), nn.AvgPool3d(2),
                                nn.Conv3d(16, 24, 3, padding=1, padding_mode="circular"), nn.SiLU(),
                                nn.AdaptiveAvgPool3d(2), nn.Flatten(),
                                nn.Linear(24*8, 32), nn.SiLU(), nn.Linear(32, nout))

        def forward(s, x):
            return s.f(x)
    return torch, nn, Fn, UNet3D, Surrogate


def cosine_schedule(T, s=0.008):
    t = np.linspace(0, T, T + 1) / T
    ab = np.cos((t + s) / (1 + s) * np.pi / 2) ** 2
    ab = ab / ab[0]
    beta = np.clip(1 - ab[1:] / ab[:-1], 1e-5, 0.999)
    return beta, np.cumprod(1 - beta)


def periodic_input(fields, size, phi_hat_min=0.75):
    """Model input: tanh-scaled field on the PERIODIC grid (size^3, duplicate face dropped).
    With circular padding the networks then live on the torus, so generated cells are exactly
    periodic by construction (the paper's zero-padded U-Net learned near-periodicity)."""
    X = fit_field_res(fields, size + 1)[:, :-1, :-1, :-1]
    return np.stack([tanh_scale(f, phi_hat_min) for f in X])[:, None].astype(np.float32)


def close_periodic(F):
    """(n, s, s, s) periodic grids -> (n, s+1, s+1, s+1) node fields with the duplicate faces."""
    F = np.concatenate([F, F[:, :1]], 1)
    F = np.concatenate([F, F[:, :, :1]], 2)
    return np.concatenate([F, F[:, :, :, :1]], 3)


def fit_field_res(fields, size):
    """Crop the duplicated face / resample so the grid is a power-of-two size for the U-Net."""
    from scipy.ndimage import zoom
    if fields.shape[1] == size:
        return fields
    return np.stack([zoom(f, size / f.shape[0], order=1) for f in fields]).astype(np.float32)


def split_idx(n, seed=0, frac=0.2):
    rng = np.random.default_rng(seed)
    p = rng.permutation(n); k = int(round(frac*n))
    return p[k:], p[:k]


def train_surrogate(data, out, epochs=60, size=32, phi_hat_min=0.75, seed=0, lr=2e-3):
    torch, nn, Fn, UNet3D, Surrogate = torch_parts()
    torch.manual_seed(seed)
    ds = load_dataset(data)
    X = periodic_input(ds["fields"], size, phi_hat_min)
    Y = np.log10(np.array([[k[key] for key in KEYS] for k in C_all_constants(ds["C"])]) / ds["Es"])
    tr, te = split_idx(len(X), seed)
    m = Surrogate(); opt = torch.optim.Adam(m.parameters(), lr)
    Xt, Yt = torch.tensor(X), torch.tensor(Y, dtype=torch.float32)
    for ep in range(epochs):
        m.train()
        for b in np.array_split(np.random.default_rng(ep).permutation(tr), max(1, len(tr)//16)):
            loss = Fn.huber_loss(m(Xt[b]), Yt[b])
            opt.zero_grad(); loss.backward(); opt.step()
    m.eval()
    with torch.no_grad():
        p = m(Xt[te]).numpy()
    E_true, E_pred = 10**Y[te], 10**p
    rep = {"test_n": len(te), "params": sum(q.numel() for q in m.parameters()),
           "MAE_rel": dict(zip(KEYS, np.abs(E_true - E_pred).mean(0).round(5).tolist())),
           "MAPE_%": dict(zip(KEYS, (100*np.abs(E_true - E_pred)/E_true).mean(0).round(2).tolist()))}
    torch.save({"state": m.state_dict(), "size": size, "phi_hat_min": phi_hat_min, "report": rep}, out)
    return rep


def train_diffusion(data, out, epochs=40, size=32, chans=(1, 4, 8, 16, 32), phi_hat_min=0.75,
                    T=500, p_uncond=0.2, with_vfrac=True, surrogate=None, lam=0.05, lr=2e-3,
                    batch=8, seed=0, device="cpu"):
    torch, nn, Fn, UNet3D, Surrogate = torch_parts()
    torch.manual_seed(seed)
    ds = load_dataset(data)
    X = periodic_input(ds["fields"], size, phi_hat_min)
    cv, stats = cond_vectors(ds["C"], ds["vfrac"], with_vfrac=with_vfrac)
    tr, te = split_idx(len(X), seed)
    beta, ab = cosine_schedule(T)
    ab_t = torch.tensor(ab, dtype=torch.float32, device=device)
    net = UNet3D(chans, cv.shape[1], T).to(device)
    opt = torch.optim.Adam(net.parameters(), lr)
    # plateau decay as in the paper; with a small dataset the epoch loss is noisy, so a short
    # patience would anneal the learning rate to nothing within a few dozen epochs
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=20, min_lr=1e-5)
    sur = None
    if surrogate:
        sck = torch.load(surrogate, weights_only=False)
        sur = Surrogate(); sur.load_state_dict(sck["state"]); sur.eval().to(device)
        for q in sur.parameters():
            q.requires_grad_(False)
        Ytrue = torch.tensor(np.log10(np.array([[k[key] for key in KEYS]
                                                for k in C_all_constants(ds["C"])]) / ds["Es"]),
                             dtype=torch.float32, device=device)
    Xt = torch.tensor(X, device=device); Ct = torch.tensor(cv, dtype=torch.float32, device=device)
    hist = []
    for ep in range(epochs):
        net.train(); tot = 0.0
        for b in np.array_split(np.random.default_rng(ep).permutation(tr), max(1, len(tr)//batch)):
            x0 = Xt[b]; cb = Ct[b].clone()
            drop = torch.rand(len(b), device=device) < p_uncond     # 20% unconditional
            cb[drop] = 0.0
            t = torch.randint(0, T, (len(b),), device=device)
            a = ab_t[t][:, None, None, None, None]
            eps = torch.randn_like(x0)
            xt = a.sqrt()*x0 + (1 - a).sqrt()*eps
            pe = net(xt, t, cb)
            loss = Fn.huber_loss(pe, eps)
            if sur is not None:                     # frozen surrogate guidance on predicted x0
                x0h = ((xt - (1 - a).sqrt()*pe) / a.sqrt()).clamp(-1, 1)
                w = a.view(-1)
                ls = (w * Fn.huber_loss(sur(x0h), Ytrue[b], reduction="none").mean(1))[~drop]
                if len(ls):
                    loss = loss + lam*ls.mean()
            opt.zero_grad(); loss.backward(); opt.step(); tot += float(loss.detach())*len(b)
        sched.step(tot/len(tr)); hist.append(tot/len(tr))
        print(f"  epoch {ep+1}/{epochs} loss {hist[-1]:.4f} lr {opt.param_groups[0]['lr']:.1e}",
              file=sys.stderr)
    torch.save({"state": net.state_dict(), "chans": list(chans), "T": T, "size": size,
                "phi_hat_min": phi_hat_min, "stats": stats, "with_vfrac": with_vfrac,
                "cond_dim": cv.shape[1], "test_idx": te.tolist(), "data": os.path.abspath(data),
                "loss": hist, "Es": ds["Es"], "nu": ds["nu"]}, out)
    return {"epochs": epochs, "final_loss": hist[-1], "train": len(tr), "test": len(te),
            "params": sum(q.numel() for q in net.parameters())}


def sample(model, C_list, vfrac_list=None, steps=None, guidance=1.0, seed=0, device="cpu", eta=1.0):
    """Generate implicit fields for each target stiffness. eta=1 with all T steps is the paper's
    ancestral DDPM sampler; fewer steps and/or eta=0 give faster DDIM sampling.
    guidance > 1 is classifier-free guidance (possible because of the 20% null training)."""
    torch, nn, Fn, UNet3D, Surrogate = torch_parts()
    ck = torch.load(model, weights_only=False)
    net = UNet3D(tuple(ck["chans"]), ck["cond_dim"], ck["T"]); net.load_state_dict(ck["state"])
    net.eval().to(device)
    T = ck["T"]; _, ab = cosine_schedule(T)
    if vfrac_list is None:
        vfrac_list = [0.3]*len(C_list)
    cv, _ = cond_vectors(np.array(C_list), np.array(vfrac_list), ck["stats"], ck["with_vfrac"])
    g = torch.Generator().manual_seed(seed)
    n = len(C_list); size = ck["size"]
    x = torch.randn((n, 1, size, size, size), generator=g).to(device)
    cvt = torch.tensor(cv, dtype=torch.float32, device=device)
    ts = np.linspace(T - 1, 0, steps or T).round().astype(int)
    with torch.no_grad():
        for i, t in enumerate(ts):
            tt = torch.full((n,), int(t), device=device, dtype=torch.long)
            e = net(x, tt, cvt)
            if guidance != 1.0:
                e0 = net(x, tt, torch.zeros_like(cvt))
                e = e0 + guidance*(e - e0)
            a = float(ab[t]); ap = float(ab[ts[i+1]]) if i + 1 < len(ts) else 1.0
            x0 = ((x - math.sqrt(1 - a)*e) / math.sqrt(a)).clamp(-1, 1)
            e = (x - math.sqrt(a)*x0) / math.sqrt(1 - a)      # noise consistent with clipped x0
            sig = eta * math.sqrt(max((1 - ap) / (1 - a) * (1 - a / ap), 0.0))
            x = math.sqrt(ap)*x0 + math.sqrt(max(1 - ap - sig**2, 0.0))*e
            if sig > 0:
                x = x + sig * torch.randn(x.shape, generator=g).to(device)
    return close_periodic(x[:, 0].cpu().numpy())


# ----------------------------------------------------------------------------------------------
# 9. Plotting
# ----------------------------------------------------------------------------------------------
def render(fields, titles, out, ncol=4):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(fields); ncol = min(ncol, n); nrow = math.ceil(n / ncol)
    fig = plt.figure(figsize=(3.0*ncol, 3.1*nrow))
    for i, (f, t) in enumerate(zip(fields, titles)):
        ax = fig.add_subplot(nrow, ncol, i + 1, projection="3d")
        mm = mesh(f)
        if mm is not None:
            v, fc = mm
            ax.plot_trisurf(v[:, 0], v[:, 1], fc, v[:, 2], color="#8fa9c9", lw=0, shade=True)
        for lim in (ax.set_xlim, ax.set_ylim, ax.set_zlim):
            lim(0, 1)
        ax.set_title(t, fontsize=8); ax.set_axis_off(); ax.set_box_aspect((1, 1, 1), zoom=0.85)
    fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)


def compare(cells, res=33, hres=24, npts=5, out_png=None):
    """Stiffness-density curves of cells vs simple cubic / BCC struts (cf. paper Fig. 9, elastic
    part only). cells: list of (label, spec); the thickness h (or strut radius) is swept."""
    refs = [("simple cubic", {"families": ["sc"], "kind": "strut"}),
            ("BCC", {"families": ["bcc"], "kind": "strut"})]
    rows = []
    for label, spec in refs + list(cells):
        hs = np.linspace(0.07, 0.2, npts) if spec.get("kind") == "strut" else np.linspace(0.1, 0.45, npts)
        for h in hs:
            sp_ = {**spec, "h": float(h)}
            f = cell_field(sp_, res)
            if not printable(f)[0]:
                continue
            _, k, v, _ = cell_stiffness(f, hres=hres)
            if k:
                rows.append({"cell": label, "h": round(float(h), 3), "vfrac": round(v, 4),
                             "E_axis_mean": round((k["E1"] + k["E2"] + k["E3"]) / 3, 5),
                             "E_dir_min": round(k["E_dir_min"], 5), "G_mean": round((k["G23"] + k["G13"] + k["G12"]) / 3, 5)})
    if out_png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(10, 4))
        for label in dict.fromkeys(r["cell"] for r in rows):
            rr = [r for r in rows if r["cell"] == label]
            v = [r["vfrac"] for r in rr]
            ax[0].plot(v, [r["E_axis_mean"] for r in rr], "o-", label=label)
            ax[1].plot(v, [r["E_dir_min"] for r in rr], "o-", label=label)
        for a_, t in zip(ax, ["mean axial modulus E/Es", "weakest-direction modulus E/Es"]):
            a_.set_xlabel("volume fraction"); a_.set_ylabel(t); a_.set_yscale("log"); a_.grid(alpha=.3)
        ax[0].legend(fontsize=8); fig.tight_layout(); fig.savefig(out_png, dpi=130); plt.close(fig)
    return rows


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def parse_spec(a):
    if a.spec:                                   # e.g. a "spec" copied from `search` output
        return json.loads(a.spec)
    spec = {"families": a.families.split(","), "mode": a.mode, "t": a.t, "h": a.h, "a": a.a,
            "kind": a.kind, "freq": [int(x) for x in a.freq.split(",")]}
    need = NPHI[a.mode]
    if len(spec["families"]) != need:
        sys.exit(f"mode {a.mode} needs {need} families, got {len(spec['families'])}")
    for f in spec["families"]:
        if f not in FAMILIES:
            sys.exit(f"unknown family {f}; see `families`")
    return spec


def parse_target(s):
    """'E=0.05' or 'E1=0.05,E2=0.05,E3=0.08,G=0.02' (relative to the solid modulus)."""
    out = {}
    for kv in s.split(","):
        k, v = kv.split("="); k = k.strip(); v = float(v)
        if k == "E":
            out.update(E1=v, E2=v, E3=v)
        elif k == "G":
            out.update(G23=v, G13=v, G12=v)
        else:
            out[k] = v
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def cellargs(q):
        q.add_argument("--families", default="gyroid")
        q.add_argument("--mode", default="single", choices=list(NPHI))
        q.add_argument("--t", type=float, default=0.5)
        q.add_argument("--h", type=float, default=0.25, help="sheet half-thickness (field units)")
        q.add_argument("--a", type=float, default=0.0, help="level-set bias")
        q.add_argument("--kind", default="sheet", choices=["sheet", "network"])
        q.add_argument("--res", type=int, default=65)
        q.add_argument("--freq", default="1,1,1", help="integer periods per axis, e.g. 1,1,2 (anisotropic)")
        q.add_argument("--spec", help="full cell spec as JSON (overrides the flags above)")

    sub.add_parser("families")
    q = sub.add_parser("cell", help="build one cell: checks, stiffness, optional STL"); cellargs(q)
    q.add_argument("--Es", type=float, default=1.0, help="solid Young's modulus (e.g. GPa)")
    q.add_argument("--nu", type=float, default=0.3)
    q.add_argument("--hres", type=int, default=32)
    q.add_argument("--stl"); q.add_argument("--cell-mm", type=float, default=10.0)
    q.add_argument("--tiles", default="1,1,1"); q.add_argument("--png")
    q = sub.add_parser("dataset"); q.add_argument("--n", type=int, default=200)
    q.add_argument("--res", type=int, default=33); q.add_argument("--hres", type=int, default=32)
    q.add_argument("--out", default="glu3d_data.npz"); q.add_argument("--seed", type=int, default=0)
    q.add_argument("--kinds", default="sheet"); q.add_argument("--Es", type=float, default=1.0)
    q.add_argument("--nu", type=float, default=0.3)
    q = sub.add_parser("search", help="parametric inverse design by homogenisation")
    q.add_argument("--target", required=True); q.add_argument("--data")
    q.add_argument("--budget", type=int, default=40); q.add_argument("--res", type=int, default=33)
    q.add_argument("--hres", type=int, default=24); q.add_argument("--kinds", default="sheet")
    q.add_argument("--density-weight", type=float, default=0.0); q.add_argument("--seed", type=int, default=0)
    q = sub.add_parser("train-surrogate"); q.add_argument("--data", required=True)
    q.add_argument("--out", default="surrogate.pt"); q.add_argument("--epochs", type=int, default=60)
    q.add_argument("--size", type=int, default=32)
    q = sub.add_parser("train"); q.add_argument("--data", required=True)
    q.add_argument("--out", default="glu3d.pt"); q.add_argument("--epochs", type=int, default=40)
    q.add_argument("--size", type=int, default=32); q.add_argument("--chans", default="1,4,8,16,32")
    q.add_argument("--phi-hat-min", type=float, default=0.75); q.add_argument("--surrogate")
    q.add_argument("--lam", type=float, default=0.05); q.add_argument("--paper-cond", action="store_true",
                   help="condition on the stiffness matrix only (no volume fraction), as in the paper")
    q.add_argument("--batch", type=int, default=8); q.add_argument("--device", default="cpu")
    q = sub.add_parser("generate"); q.add_argument("--model", required=True)
    q.add_argument("--target", help="e.g. E=0.05,G=0.02 (relative)"); q.add_argument("--vfrac", type=float, default=0.3)
    q.add_argument("--from-test", type=int, default=0, help="use N test-set stiffness matrices as targets")
    q.add_argument("--n", type=int, default=4); q.add_argument("--steps", type=int, default=500)
    q.add_argument("--eta", type=float, default=1.0, help="1 = stochastic DDPM, 0 = deterministic DDIM")
    q.add_argument("--guidance", type=float, default=1.0); q.add_argument("--seed", type=int, default=0)
    q.add_argument("--out", default="generated.npz"); q.add_argument("--device", default="cpu")
    q = sub.add_parser("evaluate", help="success rate, periodicity, diversity, stiffness error")
    q.add_argument("--gen", required=True); q.add_argument("--data")
    q.add_argument("--hres", type=int, default=24); q.add_argument("--no-fem", action="store_true")
    q = sub.add_parser("stl", help="export a generated/dataset cell as a tiled watertight STL")
    q.add_argument("--npz", required=True); q.add_argument("--index", type=int, default=0)
    q.add_argument("--out", default="lattice.stl"); q.add_argument("--cell-mm", type=float, default=10.0)
    q.add_argument("--tiles", default="3,3,3")
    q = sub.add_parser("compare", help="stiffness vs density against simple cubic and BCC")
    q.add_argument("--cells", default='[["gyroid sheet", {"families": ["gyroid"]}]]',
                   help="JSON list of [label, spec]")
    q.add_argument("--npz", help="also compare cells from a dataset/generated npz (with --index)")
    q.add_argument("--index", default="0"); q.add_argument("--png", default="compare.png")
    q.add_argument("--hres", type=int, default=24)
    q = sub.add_parser("render"); q.add_argument("--npz", required=True)
    q.add_argument("--n", type=int, default=8); q.add_argument("--out", default="cells.png")
    a = p.parse_args()

    if a.cmd == "families":
        print(json.dumps({"families": list(FAMILIES), "modes": NPHI,
                          "note": "hybrids blend 2-4 families with Eqs. 3-7 of the paper"}, indent=1))
    elif a.cmd == "cell":
        spec = parse_spec(a)
        f = cell_field(spec, a.res)
        ok, info = printable(f)
        res = {"spec": spec, "printable": ok, **info, "periodicity_error": periodicity(f)}
        if ok:
            C, k, vf, _ = cell_stiffness(f, a.Es, a.nu, a.hres, verbose=True)
            res["C"] = np.round(C, 6).tolist()
            res["constants"] = {kk: round(v, 6) for kk, v in k.items()}
            res["specific_E_mean"] = round((k["E1"] + k["E2"] + k["E3"]) / 3 / vf, 5)
        if a.stl:
            mm = mesh(f, a.cell_mm, tuple(int(x) for x in a.tiles.split(",")))
            m = save_stl(*mm, a.stl)
            res["stl"] = {"path": a.stl, "watertight": bool(m.is_watertight),
                          "volume_mm3": round(float(m.volume), 2), "triangles": int(len(m.faces))}
        if a.png:
            render([f], [f"{'+'.join(spec['families'])} {spec['mode']}"], a.png, 1)
        print(json.dumps(res, indent=1))
    elif a.cmd == "dataset":
        print(json.dumps(make_dataset(a.n, a.res, a.out, a.seed, tuple(a.kinds.split(",")),
                                      a.Es, a.nu, a.hres), indent=1))
    elif a.cmd == "search":
        out = search(parse_target(a.target), a.data, a.res, a.hres, a.budget, a.seed,
                     kinds=tuple(a.kinds.split(",")), density_weight=a.density_weight)
        print(json.dumps({"target": parse_target(a.target), "best": out}, indent=1))
    elif a.cmd == "train-surrogate":
        print(json.dumps(train_surrogate(a.data, a.out, a.epochs, a.size), indent=1))
    elif a.cmd == "train":
        print(json.dumps(train_diffusion(a.data, a.out, a.epochs, a.size,
                                         tuple(int(x) for x in a.chans.split(",")), a.phi_hat_min,
                                         with_vfrac=not a.paper_cond, surrogate=a.surrogate,
                                         lam=a.lam, batch=a.batch, device=a.device), indent=1))
    elif a.cmd == "generate":
        import torch
        ck = torch.load(a.model, weights_only=False)
        if a.from_test:
            ds = load_dataset(ck["data"]); idx = ck["test_idx"][:a.from_test]
            Cl, vl, src = ds["C"][idx], ds["vfrac"][idx], idx
        else:
            tgt = parse_target(a.target or "E=0.05")
            E = [tgt.get(k, np.mean([tgt.get(x, 0.05) for x in ("E1", "E2", "E3")])) for k in ("E1", "E2", "E3")]
            G = [tgt[k] for k in ("G23", "G13", "G12")] if "G23" in tgt else None
            Cl = np.array([target_C(np.array(E)*ck["Es"], None if G is None else np.array(G)*ck["Es"], 0.3)]*a.n)
            vl, src = np.full(a.n, a.vfrac), None
        F = sample(a.model, Cl, vl, a.steps, a.guidance, a.seed, a.device, a.eta)
        np.savez_compressed(a.out, fields=F, target_C=np.array(Cl), target_vfrac=np.array(vl),
                            Es=ck["Es"], nu=ck["nu"], src=np.array(src if src is not None else []))
        print(json.dumps({"out": a.out, "n": len(F), "success": [success(f) for f in F]}, indent=1))
    elif a.cmd == "evaluate":
        g = np.load(a.gen)
        F = g["fields"]; res = {"n": len(F)}
        ok = [success(f) for f in F]
        res["success_rate_%"] = 100*float(np.mean(ok))
        res["periodicity_error_mean"] = float(np.mean([periodicity(f) for f in F]))
        res["vfrac_mean"] = float(np.mean([voxels(f).mean() for f in F]))
        if a.data:
            ds = load_dataset(a.data)
            tr = fit_field_res(ds["fields"], F.shape[1])
            sel = np.random.default_rng(0).choice(len(tr), min(60, len(tr)), replace=False)
            res.update(diversity([f for f, o in zip(F, ok) if o], [tr[i] for i in sel]))
        if not a.no_fem and "target_C" in g.files:
            errs = []
            for f, o, Ct in zip(F, ok, g["target_C"]):
                if not o:
                    continue
                pv, _ = keep_largest(periodic_voxels(f, a.hres if f.shape[0] - 1 > a.hres else None))
                Cg = homogenize(pv*float(g["Es"]), float(g["nu"]))
                if np.linalg.cond(Cg) > 1e12:
                    continue
                kg, kt = constants(Cg), constants(Ct)
                errs.append({k: abs(kg[k] - kt[k]) / kt[k] for k in KEYS})
            if errs:
                res["stiffness_rel_err_mean"] = {k: round(float(np.mean([e[k] for e in errs])), 3) for k in KEYS}
                res["fem_checked"] = len(errs)
        print(json.dumps(res, indent=1))
    elif a.cmd == "stl":
        d = np.load(a.npz)
        f = d["fields"][a.index]
        mm = mesh(f, a.cell_mm, tuple(int(x) for x in a.tiles.split(",")))
        if mm is None:
            sys.exit("no surface at level set 0")
        m = save_stl(*mm, a.out)
        print(json.dumps({"out": a.out, "watertight": bool(m.is_watertight),
                          "volume_mm3": round(float(m.volume), 2),
                          "bbox_mm": np.round(m.extents, 2).tolist()}, indent=1))
    elif a.cmd == "compare":
        cells = [(l_, sp_) for l_, sp_ in json.loads(a.cells)]
        if a.npz:
            d = np.load(a.npz, allow_pickle=False)
            sp = json.loads(str(d["specs"]))
            cells += [(f"#{i} " + "+".join(sp[i]["families"]) + f" {sp[i]['mode']}", sp[i])
                      for i in map(int, a.index.split(","))]
        print(json.dumps(compare(cells, hres=a.hres, out_png=a.png), indent=1))
    elif a.cmd == "render":
        d = np.load(a.npz, allow_pickle=False)
        F = d["fields"][:a.n]
        titles = [f"#{i}" for i in range(len(F))]
        if "specs" in d.files:
            sp = json.loads(str(d["specs"]))
            titles = [f"{'+'.join(x['families'])} ({x['mode']})"[:34] for x in sp[:len(F)]]
        render(F, titles, a.out)
        print(json.dumps({"out": a.out}))


if __name__ == "__main__":
    main()
