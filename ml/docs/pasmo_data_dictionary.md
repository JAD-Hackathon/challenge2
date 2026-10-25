# Data Dictionary: PASMO Radar Dataset

> Proxy dataset used to build and test the ML pipeline before the Aveiro Tech City Living Lab data arrives.

## 1. Provenance

| Item | Value |
|---|---|
| Name | Mobility Patterns of a Coastal Area Using Traffic Classification Radars |
| File | `pasmo_dataset.csv` (about 19 MB) |
| Source | Figshare: `https://figshare.com/s/d324f5be912e7f7a0d21` |
| Paper | Ferreira et al., *Data* 2022, 7(7), 97, DOI `10.3390/data7070097` |
| License | CC BY 4.0 (cite the paper) |
| Project | PASMO (Instituto de Telecomunicações, Univ. of Aveiro), open living lab for C-ITS |
| Area | Beaches of **Barra** and **Costa Nova** (Ílhavo/Aveiro), summer resorts plus commuter "dormitory" villages |
| Sensors | 3 traffic radars (smartmicro UMRR-0C Type 42, 24 GHz). Radar 1: before the bridge; radar 2: connection segment between Barra and Costa Nova; radar 3: south urban limit of Costa Nova |
| Records | 74,305 rows, each aggregating **10 minutes** |
| Underlying data | Raw radar telemetry at 100 ms sampling (about 155 million radar records, 2020 to 2021), aggregated by the authors. Parking-sensor data are **not** included |

## 2. What this dataset is and is not

**It is:** pre-aggregated 10-minute traffic summaries per radar: speeds of objects approaching and leaving, plus two derived net-flow indicators, one per region.

**It is not (despite the abstract wording):**
- Not row-level detections. You cannot re-aggregate to 15 minutes without interpolation.
- No vehicle-type columns (heavy, light, two-wheeler) and no pedestrian counts appear in the documented schema.
- No coordinates in the documented final schema.
- No weather and no COVID columns. The paper only says they can be joined from outside sources (Appendix B and C list holidays, local feasts and COVID restrictions).

## 3. Schema

### 3.1 Index columns

| Column | Type | Description | Notes |
|---|---|---|---|
| `year` | int | Year of record | 2020-2021 |
| `month` | int | Month | 1-12 |
| `day` | int | Day of month | 1-31 |
| `hour` | int | Hour | 0 to 23 |
| `minute` | int | Ten-minute interval label | Paper lists intervals as 0–10, 11–20, 21–30, 31–40, 41–50, 51–60; equations use `0, 10, … 50` (6 distinct values) |
| `wd` | int | Weekday | Added by authors "for ease of query writing". Encoding (0 start, Monday or Sunday first) |

Timestamp is **not** a single column. Build it from year, month, day, hour, minute. Timezone is unspecified.

### 3.2 Speed columns (per radar `i` = 1, 2, 3)

Naming: `Speed_{stat}_{dir}R{i}`

| Pattern | Meaning | Unit |
|---|---|---|
| `Speed_med_ARi` | Mean speed of objects **approaching** radar *i* | m/s |
| `Speed_max_ARi` | Maximum speed approaching radar *i* | m/s |
| `Speed_min_ARi` | Minimum speed approaching radar *i* | m/s |
| `Speed_med_DRi` | Mean speed of objects **moving away** from radar *i* (detaching) | m/s |
| `Speed_max_DRi` | Maximum speed moving away from radar *i* | m/s |
| `Speed_min_DRi` | Minimum speed moving away from radar *i* | m/s |

That is 6 columns × 3 radars = **18 speed columns**.

Notes:
- Units are **m/s**, not km/h. Convert (× 3.6) for the app and for the risk score.
- "max" and "min" over a 10-minute window are sensitive to radar noise and outliers.
- If no object passed in a direction during the window, the speed columns are probably 0.

### 3.3 Traffic-flow columns

| Column | Description | Unit |
|---|---|---|
| `TF_Barra` | Net traffic flow in the Barra region | objects / 10 min |
| `TF_Costa` | Net traffic flow in the Costa Nova region | objects / 10 min |

Important:
- These are **net flows (differences)**, built from counts of objects approaching minus detaching. They can be **negative**.
- They are **not** vehicle counts. A busy road with equal traffic in both directions gives a value near 0.
- Paper: a positive value means an increase in traffic in that region, a negative value a reduction. Cumulative sum of TF over a day is used by the authors as a proxy of vehicles present.
- Formula in the paper: `TF_Barra = (QAR1 + QDR2) − (QDR1 + QAR2)`. The printed formula for `TF_Costa` looks wrong (`(QAR2 + QAR3) − (QAR2 + QDR3)` cancels `QAR2`), probably a typo. Do not try to reproduce it; use the columns as given.
- Raw counts per direction (`QARi`, `QDRi`) are **not** included in the final file, so you cannot recover total volume.

Reference statistics from the paper (Table 1), useful as a sanity check:

| Statistic | `TF_Barra` | `TF_Costa` |
|---|---|---|
| Mean | 0.19 | −3.61 |
| Std | 20.29 | 14.45 |
| Min | −187 | −133 |
| 25% | −7 | −8 |
| 50% | 0 | −0.88 |
| 75% | 9 | 2 |
| Max | 155 | 109 |

## 4. Coverage and gaps

- 74,305 rows × 10 min ≈ **516 days** of data.
- The raw telemetry doesn't cover 2019 to 2021 but 2020 to 2021. So, the CSV spans that whole period (about 1,095 days, 157,680 ten-minute slots).
- 2020 and 2021 contain COVID-19 lockdown and movement bans (Appendix C of the paper, for example national lockdown from 19 March 2020 and municipality movement bans on 29 Oct to 2 Nov 2020). Traffic in these periods is atypical: flag it, do not blindly mix with normal periods.

## 5. Mapping to our standard schema

Our pipeline uses one standard schema for every dataset. PASMO maps as follows:

| Standard column | From PASMO | Comment |
|---|---|---|
| `ts` | `year, month, day, hour, minute` | Start of the 10-min bin; localize timezone after verifying |
| `sensor_id` | `barra`, `costa` (for TF) or `radar_1..3` (for speeds) | Two levels; see below |
| `flow_net` | `TF_Barra`, `TF_Costa` | Net flow, can be negative |
| `speed_mean_in_ms` | `Speed_med_ARi` | One column per radar, convert to km/h downstream |
| `speed_mean_out_ms` | `Speed_med_DRi` | |
| `speed_max_in/out`, `speed_min_in/out` | other speed columns | |
| `vehicles` | not available | Do not fabricate. Leave NaN |
| `peds` | not available | Same |

**Long format:** reshape to one row per `(ts, sensor_id)` with sensors `radar_1..3` (speed stats) and `barra`, `costa` (flow). Keep the wide file in `data/raw/` untouched.

## 6. Consequences for the ML plan

| Earlier assumption | PASMO reality | Change |
|---|---|---|
| 15-minute bins | Native resolution is **10 min** | Use 10-min bins; horizons 10, 30, 60 min (1, 3, 6 steps). Do not resample to 15 min |
| Lags 96 (day) and 672 (week) | 144 steps per day, 1008 per week | Lags 1, 3, 6, **144**, **1008** |
| Target = vehicle count | Only net flow `TF_*` and speeds | Forecast `TF_Barra`, `TF_Costa` and mean speed. Since TF is signed, also consider `abs(TF)` as an "activity" target |
| Pedestrian risk score | No pedestrians, no vehicle types | **Cannot be built on PASMO**. Test the risk code on synthetic input or on another proxy; the real Living Lab data should contain pedestrian data |
| Per-class counts | Not available | Skip class-based features on this proxy |
| Weather features | Not in file | Join from an external weather source for Aveiro, or skip for the proxy |
| Holidays | Not in file | Use `holidays.Portugal()` plus local feasts (Costa Nova, Senhor dos Navegantes, Saint John, Saint Peter) from the paper's Appendix B |

Seasonality note: this is a **beach-access** area. Summer weekends and good weather drive peaks, so month and weather will matter much more than in a city centre. Do not expect proxy results to transfer 1:1 to central Aveiro.

## 9. How this will differ from the real Living Lab data

Placeholders to fill in at the hackathon, using the same structure as this file:

- Sampling interval and whether data is raw detections or pre-aggregated
- Vehicle typology, pedestrian counts, crosswalk identifiers
- Sensor coordinates and segment IDs
- Timezone and timestamp format
- Parking: per lot or per space, capacity field
- Units (m/s vs km/h)