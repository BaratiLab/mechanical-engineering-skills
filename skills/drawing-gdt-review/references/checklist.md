# Drawing review checklist

## Title block & notes
- [ ] Part number, revision, title, material (with spec/condition), finish/coating, scale, units, projection symbol
- [ ] General tolerance note (ISO 2768-mK or a block-tolerance table)
- [ ] Standard note (ASME Y14.5-2018 / ISO 8015)
- [ ] Edge-break, deburr, and surface-finish defaults (Ra)
- [ ] Heat treatment / hardness, with the test location if relevant
- [ ] Revision table matches the revision letter

## Views
- [ ] Enough views to define every feature without ambiguity, and no redundant views
- [ ] Hidden lines only where they clarify
- [ ] Section views labelled; cutting-plane arrows point the right way
- [ ] Detail views labelled, with scale stated

## Dimensioning
- [ ] Every feature fully defined in size and location (no missing dimensions)
- [ ] No double dimensioning (over-constraint) unless marked as reference (in parentheses)
- [ ] No chained dimensions where a stack-up matters; dimension from datums instead
- [ ] Dimensions are on the view where the feature shows its true shape
- [ ] Diameters on the longitudinal view for turned parts; radii called out correctly
- [ ] Hole callouts complete: Ø, depth, thread spec (M6×1-6H), counterbore/countersink, quantity (4×)
- [ ] Units consistent; decimal places follow convention (inch: places imply tolerance; metric: no trailing zeros in ASME)

## GD&T
- [ ] Datum features chosen by function; datum feature symbols placed on surfaces or features of size correctly
- [ ] Feature control frames are syntactically valid: symbol | tol (Ø if cylindrical zone) | modifiers | datums
- [ ] Basic dimensions boxed for every positioned or profiled feature
- [ ] Modifiers (Ⓜ Ⓛ Ⓕ Ⓟ) used only where valid
- [ ] Tolerance hierarchy: form ≤ orientation ≤ location ≤ size
- [ ] Composite / multiple single-segment frames read correctly
- [ ] No obsolete symbols (concentricity, symmetry) under Y14.5-2018

## Manufacturability & inspection
- [ ] Tolerances achievable by the intended process
- [ ] Every critical dimension measurable (with a datum simulator possible)
- [ ] Threads, inserts, and keyways call out standards
- [ ] Surface finish specified on mating and sealing surfaces
