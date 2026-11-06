# Data sources — the shopping list

Every series the pipeline expects, where it comes from, and the file to drop into `data/raw/`.
File format for all of them: CSV with two columns, `period,value`
(`2024-01` for monthly, `2024Q1` for quarterly), one row per period, levels as published.

Nothing below can be fetched from inside the Claude sandbox (no outbound network to these hosts),
so fetch on your own machine with `scripts/fetch_sources.py` or by hand. URLs and series codes
are from memory and **must be verified** [ต้องตรวจ] before you rely on them.

## Targets

| file | series | source | how |
|---|---|---|---|
| `gdp_yoy.csv` | real GDP growth, y-o-y % | NESDC (สภาพัฒน์) https://www.nesdc.go.th | QGDP press release, Excel table of GDP at chained volume. Collecting the *first-release* value from each quarterly press release (≈45 PDFs since 2015) gives true real-time vintages — strongly recommended, see paper §7 |
| `gdp_qoq_sa.csv` | real GDP growth, q-o-q SA % | NESDC | same release |
| `cpi_yoy.csv` | headline CPI, y-o-y % | TPSO, Ministry of Commerce https://www.price.moc.go.th | monthly CPI report |

## Hard data (monthly)

| file | series | source | how |
|---|---|---|---|
| `mpi.csv` | Manufacturing Production Index | OIE https://www.oie.go.th | industrial statistics → MPI (xlsx) |
| `pci.csv`, `pii.csv` | private consumption / investment indices | BOT https://apiportal.bot.or.th | BOT API (free key); `scripts/fetch_sources.py bot` |
| `credit.csv` | commercial-bank loans outstanding | BOT API | financial institutions statistics |
| `promptpay.csv` | PromptPay transaction value | BOT https://www.bot.or.th | payment systems statistics (monthly xlsx) |
| `exports.csv`, `imports.csv` | merchandise trade, USD | Customs Department https://www.customs.go.th | trade statistics; MOC also publishes a monthly press release |
| `tourists.csv` | international arrivals | MOTS https://www.mots.go.th | tourism statistics (monthly) |
| `aot_pax.csv` | AOT passengers, all airports | AOT https://www.airportthai.co.th | air traffic statistics |
| `electricity.csv` | electricity consumption | EPPO https://www.eppo.go.th | energy statistics → electricity |
| `vehicle_reg.csv` | new vehicle registrations | DLT https://web.dlt.go.th/statistics | monthly registrations |
| `expressway.csv` | expressway traffic | EXAT https://www.exat.co.th | traffic volume statistics |
| `oil_retail.csv` | retail diesel price (monthly mean) | EPPO / PTT | daily retail prices, averaged |
| `agri_price.csv` | farm price index | OAE https://www.oae.go.th | price indices |

## Alternative data

| file | series | source | how |
|---|---|---|---|
| `gt_*.csv` | Google Trends, Thailand | https://trends.google.com | `scripts/fetch_sources.py trends` (pytrends; weekly → monthly mean; keep the comparison baseline fixed) |
| `nightlights.csv` | VIIRS monthly radiance, national sum | NASA Black Marble VNP46A3 https://ladsweb.modaps.eosdis.nasa.gov | Earthdata login; zonal sum per province (GADM level 1), then national total; `scripts/fetch_sources.py lights` sketches it |
| `no2.csv` | tropospheric NO2 column, industrial provinces | Sentinel-5P via Google Earth Engine `COPERNICUS/S5P/OFFL/L3_NO2` | monthly mean over EEC provinces + Samut Prakan |
| `online_prices.csv` | online price index | own scraper | daily prices of a fixed basket from large online grocers (check each site's terms of service) |
| `mobility.csv` | Google Community Mobility, retail & recreation | https://www.google.com/covid19/mobility (archive) | national TH rows, monthly mean; series ended 2022-10 |

## Release calendar

`release_lag_days` in `config/indicators.yaml` is the typical number of days between the end
of the reference period and publication. The values are reasonable approximations; before a
real evaluation, replace them with the actual release dates (each agency publishes a calendar)
or, better, add a `release` column to the CSV with the exact publication date and extend
`Panel.from_series` to use it.

## Minimal real-data start

You do not need everything. The pipeline runs with any subset: put the files you have in
`data/raw/`, leave the rest missing, and `make data` loads real where present and
`synthetic_*` elsewhere — each synthetic substitute is announced loudly. A credible first
real run needs `gdp_yoy.csv`, `cpi_yoy.csv`, `mpi.csv`, `exports.csv`, `tourists.csv`,
`oil_retail.csv` and the `gt_*.csv` set.
