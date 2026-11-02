# Should-cost model

Per part (unit):  material + conversion + tooling

- **material** = mass × price / (1 − scrap)
- **conversion** = cycle_s / 3600 × machine rate / cavities
- **tooling** = tooling USD / (annual volume × lifetime years)

Product:  should-cost = Σ parts + assembly labour (DFA time × labour rate)

If `cost_usd` is given (a quote, a catalogue price, or a purchased-part estimate), it replaces the
model for that part. Use it for motors, PCBAs, switches, bearings, chucks, batteries, and fasteners.

## Inputs that matter most
1. **Annual volume.** At 10 k/yr a $60 k mold adds $2 per part over 3 years. At 1 M/yr it adds $0.02.
2. **Purchased parts.** These usually dominate in electromechanical products; get real quotes.
3. **Cycle time.** For molding this is set by the thickest wall: about 2 s per mm² of wall thickness
   (in mm) for cooling as a first guess.
4. **Labour rate.** Use the rate where it is assembled: roughly $4–10/h in South and Southeast Asia
   and China coastal plants, $25–45/h in the US and Western Europe (fully loaded, indicative).

## Defaults in the script (override per part or in `product.material_usd_kg`)
Material prices (USD/kg) and process tables are in `scripts/teardown.py` (`MATERIAL_USD_KG`,
`PROCESS`). They are order-of-magnitude 2025–26 values for ranking parts against each other, not for
quoting. Check current resin and metal indices when cost matters.

| Process | Rate $/h | Default cycle s | Default tooling $ | Scrap |
|---|---|---|---|---|
| injection_molding | 45 | 30 | 25 000 | 3 % |
| overmolding | 55 | 45 | 40 000 | 4 % |
| die_casting | 90 | 45 | 60 000 | 5 % |
| stamping | 80 | 2 | 15 000 | 10 % |
| progressive_die | 110 | 0.8 | 40 000 | 10 % |
| cnc_turning | 70 | 90 | 0 | 2 % |
| cnc_milling | 85 | 300 | 0 | 2 % |
| powder_metallurgy | 70 | 10 | 20 000 | 2 % |
| sheet_metal | 70 | 60 | 500 | 5 % |
| forging | 100 | 20 | 30 000 | 5 % |
| fdm / sls | 5 / 40 | 3600 / 900 | 0 | 5 % |

## Sanity checks
- For mass-market consumer hardware, should-cost is usually 25–40 % of retail. Below 15 % means
  costs are missing; above 60 % means the volume or rates are wrong.
- Purchased parts usually make 50–80 % of the cost of electromechanical products.
- If one molded part costs more than about $3, check the cycle time and the cavity count.
