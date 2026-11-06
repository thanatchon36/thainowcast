| id | series | source | group | freq | first | last | lag (days) | transform | status |
|---|---|---|---|---|---|---|---|---|---|
| gdp_yoy | Real GDP growth, y-o-y (%) | NESDC | target | Q | 2005Q1 | 2026Q3 | 48 | level | SYNTHETIC |
| gdp_qoq_sa | Real GDP growth, q-o-q seasonally adjusted (%) | NESDC | target | Q | 2005Q1 | 2026Q3 | 48 | level | SYNTHETIC |
| cpi_yoy | Headline CPI inflation, y-o-y (%) | TPSO | target | M | 2005-01 | 2026-10 | 6 | level | SYNTHETIC |
| mpi | Manufacturing Production Index | OIE (.) | hard | M | 2004-01 | 2026-10 | 30 | yoy | SYNTHETIC |
| pci | Private Consumption Index | BOT (.) | hard | M | 2004-01 | 2026-10 | 30 | yoy | SYNTHETIC |
| pii | Private Investment Index | BOT (.) | hard | M | 2004-01 | 2026-10 | 30 | yoy | SYNTHETIC |
| credit | Commercial bank loans outstanding | BOT (.) | hard | M | 2004-01 | 2026-10 | 30 | yoy | SYNTHETIC |
| promptpay | PromptPay transaction value | BOT (.) | hard | M | 2016-01 | 2026-10 | 30 | yoy | SYNTHETIC |
| exports | Merchandise exports (USD) | Customs Department | hard | M | 2004-01 | 2026-10 | 25 | yoy | SYNTHETIC |
| imports | Merchandise imports (USD) | Customs Department | hard | M | 2004-01 | 2026-10 | 25 | yoy | SYNTHETIC |
| tourists | International tourist arrivals | MOTS | hard | M | 2004-01 | 2026-10 | 20 | log_yoy | SYNTHETIC |
| aot_pax | AOT airport passengers | AOT (.) | hard | M | 2004-01 | 2026-10 | 20 | log_yoy | SYNTHETIC |
| electricity | Electricity consumption | EPPO (.) | hard | M | 2004-01 | 2026-10 | 45 | yoy | SYNTHETIC |
| vehicle_reg | New vehicle registrations | DLT | hard | M | 2004-01 | 2026-10 | 15 | yoy | SYNTHETIC |
| expressway | Expressway traffic volume | EXAT (.) | hard | M | 2004-01 | 2026-10 | 30 | yoy | SYNTHETIC |
| oil_retail | Retail diesel price (monthly average) | EPPO (.) / PTT | hard | M | 2004-01 | 2026-10 | 1 | yoy | SYNTHETIC |
| agri_price | Farm price index | OAE (.) | hard | M | 2004-01 | 2026-10 | 15 | yoy | SYNTHETIC |
| gt_unemploy | Google Trends: unemployment / job search (TH) | Google Trends | alt_trends | M | 2008-01 | 2026-10 | 3 | yoy_diff | SYNTHETIC |
| gt_loan | Google Trends: loan / borrowing (TH) | Google Trends | alt_trends | M | 2008-01 | 2026-10 | 3 | yoy_diff | SYNTHETIC |
| gt_car_installment | Google Trends: car installment (TH) | Google Trends | alt_trends | M | 2008-01 | 2026-10 | 3 | yoy_diff | SYNTHETIC |
| gt_travel | Google Trends: travel / hotel booking (TH) | Google Trends | alt_trends | M | 2008-01 | 2026-10 | 3 | yoy_diff | SYNTHETIC |
| gt_prices | Google Trends: prices / fuel price (TH) | Google Trends | alt_trends | M | 2008-01 | 2026-10 | 3 | yoy_diff | SYNTHETIC |
| nightlights | Nighttime lights radiance, national sum (VNP46A3) | NASA Black Marble | alt_lights | M | 2012-04 | 2026-10 | 40 | log_yoy | SYNTHETIC |
| no2 | Tropospheric NO2 column, industrial provinces (Sentinel-5P) | ESA Copernicus | alt_no2 | M | 2018-07 | 2026-10 | 5 | log_yoy | SYNTHETIC |
| online_prices | Online price index (scraped daily, Billion-Prices style) | own scraper | alt_prices | M | 2015-01 | 2026-10 | 1 | yoy | SYNTHETIC |
| mobility | Google Community Mobility: retail & recreation (% vs baseline) | Google (discontinued 2022-10) | alt_mobility | M | 2020-02 | 2022-10 | 2 | level | SYNTHETIC |