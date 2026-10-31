# controlDict function objects that produce evidence (OpenFOAM Foundation v11–v14)

Add these to `system/controlDict` → `functions { ... }`. Check the names against your version with `foamPostProcess -list`.

```cpp
functions
{
    // field positivity / finiteness -> evidence.py minmax
    #includeFunc fieldMinMax(p, T, rho)

    // domain mass M_n written EVERY step -> transient closure
    domainMass
    {
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        fields          (rho);
        operation       volIntegrate;
        writeControl    timeStep;
        writeInterval   1;
        writeFields     false;
    }

    // net boundary mass flux Phi_n (sum of phi over each open patch), every step
    inletFlux  { type surfaceFieldValue; libs ("libfieldFunctionObjects.so"); select patch; patch inlet;
                 fields (phi); operation sum; writeControl timeStep; writeInterval 1; writeFields false; }
    outletFlux { $inletFlux; patch outlet; }
    wallFlux   { $inletFlux; patch obstacle; }      // wall impermeability check

    // steady monitors -> evidence.py drift
    #includeFunc patchAverage(name=outlet, p)
    #includeFunc patchFlowRate(patch=outlet)

    // bluff-body forces -> evidence.py growth
    forces { type forces; libs ("libforces.so"); patches (cube); rho rhoInf; rhoInf 1; CofR (0 0 0);
             writeControl timeStep; writeInterval 1; }
}
```

## Building `mass_records.csv` for `evidence.py closure`
Columns: `t,dt,M,Phi,segment,inflow,outflow`, where
- `M` = domainMass volIntegrate(rho) at step n;
- `Phi` = inletFlux + outletFlux (+ any other open patch), positive outward;
- `segment` = restart index. Increment it whenever the run is restarted, so seam pairs are never differenced;
- `inflow`, `outflow` = |inletFlux|, |outletFlux| (used for normalization).

For a 2-D case with an `empty` direction, use the same span for every term; normalization cancels it.

## Line sample for the step front
```cpp
#includeFunc graphUniform(funcName=frontLine, start=(0 0.1 0), end=(0.6 0.1 0), nPoints=480, fields=(p rho T))
```
Convert the last time's output to `x,p,rho,T` CSV and run `evidence.py front --step-x 0.6`.
