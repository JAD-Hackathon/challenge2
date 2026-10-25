# Smart Aveiro: Codebase Preparation Plan (ML first)

**Goal:** arrive at the hackathon with a working, tested pipeline skeleton, so that on day 1 the only job is to plug in the real Living Lab data and the work is retraining, not rewriting.

**Principle:** the real datasets arrive late and their format is unknown. Prepare everything that does *not* depend on their exact format: structure, contracts, loaders behind interfaces, features, baselines, evaluation, Docker, and a fake-predictions generator for the API and app teams.

---

## 0. Definition of "ready"

By the start of the hackathon we want:

- [✓] `ml/` repo structure committed, with `README.md` and `requirements.txt`
- [ ] One command runs the full chain: `prepare_data → train → evaluate → predict`
- [ ] Pipeline demonstrated end to end on **proxy data** (traffic, pedestrians, parking)
- [ ] `data/predictions/latest.parquet` follows the agreed **data contract**
- [ ] A fake `latest.parquet` generator exists, so the API and app teams are never blocked
- [ ] Baseline + XGBoost backtest table produced on proxy data
- [ ] `ml/Dockerfile` builds and runs `predict.py`
- [ ] Day-1 checklist and mentor questions printed

---

## 1. Proxy datasets

| Vertical | Dataset | Why it fits | Notes |
|---|---|---|---|
| Traffic + pedestrians + speed | **PASMO radar dataset** (Aveiro region, 3 traffic classification radars, 2 years; speed, position, type: heavy, light, two-wheeler, pedestrian) | Same region and the same kind of sensor as the Living Lab | Figshare: `https://figshare.com/s/d324f5be912e7f7a0d21`. Paper: *Dataset: Mobility Patterns of a Coastal Area Using Traffic Classification Radars*, MDPI *Data*, 2022. **Best proxy: start here.** |
| Parking occupancy | **Parking Birmingham** (UCI id 482; `SystemCodeNumber`, `Capacity`, `Occupancy`, `LastUpdated`; 2016-10-04 to 2016-12-19, 8:00 to 16:30; has missing values; CC BY 4.0) | Occupancy per lot over time, which is the exact shape of a smart-parking feed | `pip install ucimlrepo` then `fetch_ucirepo(id=482)`, or download `dataset.csv` (about 1.4 MB). Short history: good for pipeline testing, not for judging model quality. |
| Parking (richer) | **Melbourne on-street parking sensors** (City of Melbourne open data, in-ground sensor events) | Event-level data, useful to practise converting events to occupancy | Large (millions of records). Optional. |
| Traffic counts | Kaggle: search "traffic volume", e.g. *Metro Interstate Traffic Volume* | Hourly counts plus weather, good for lag/weather features | Check the exact name and licence on Kaggle before using. |
| Pedestrians / footfall | Kaggle / City of Melbourne: *Pedestrian Counting System* | Sensor-level hourly footfall, good for the tourism/risk signal | Check availability and licence. |

---

## 2. Repository layout

```
ml/
├── README.md
├── requirements.txt
├── Dockerfile
├── Makefile                  # scripts
├── configs/
│   └── base.yaml             # bin size, horizons, feature list, model params, paths
├── data/
│   ├── README.md             # where each dataset comes from
│   ├── raw/                  # never edited
│   ├── interim/              # cleaned, row-level (parquet)
│   ├── processed/            # aggregated + features (parquet)
│   └── predictions/          # output consumed by the API
├── docs/
│   ├── architecture/         # pipeline diagram, data_contract.md
│   └── data_dictionary.md    # one section per dataset
├── models/                   # joblib artifacts + metrics.json (gitignored)
├── notebooks/
├── scripts/
│   ├── prepare_data.py
│   ├── train.py
│   ├── evaluate.py
│   ├── predict.py
│   └── make_fake_predictions.py
├── src/
│   ├── config.py
│   ├── data/                 # loaders (one per dataset), cleaning, aggregate
│   ├── features/             # temporal.py, weather.py
│   ├── models/               # baseline.py, boosted.py, statistical.py
│   ├── evaluation/           # backtest.py
│   └── risk/                 # pedestrian.py
└── tests/
```

Run everything from `ml/` as modules: `python -m scripts.train`.

---

## 3. Data contract

File: `ml/docs/architecture/data_contract.md`. The API only reads this table.

| Column | Type | Description |
|---|---|---|
| `sensor_id` | string | Sensor or zone identifier |
| `metric` | string | Metric being predicted; availability must be confirmed |
| `target_ts` | timestamp (UTC) | Target prediction time |
| `horizon_min` | int | Forecast horizon in minutes |
| `value` | float | Predicted value |
| `lower_80` / `upper_80` | float, nullable | Optional prediction interval bounds |
| `model_version` | string | Model identifier |
| `generated_at` | timestamp (UTC) | Forecast generation time |

Also define a **sensors table** (`sensor_id, lat, lon, type, name`) so the API can place every prediction on the map.

---

## 4. Work phases

### Phase A: Foundations
- [✓] Create repo structure, `requirements.txt` (pandas, pyarrow, scikit-learn, statsmodels, xgboost, holidays, joblib, pyyaml, matplotlib, pytest)
- [ ] Write `data_contract.md` and `data_dictionary.md` skeleton
- [ ] Implement `src/config.py` (paths, bin size, horizons loaded from YAML)
- [ ] Write `make_fake_predictions.py` and **hand it to the API/app teams**
- [✓] `.gitignore` for `data/*`, `models/*` (keep `.gitkeep`)

**Done when:** API team can read a fake `latest.parquet`.

### Phase B: Ingestion and aggregation (PASMO)
- [ ] Notebook `01_explore_pasmo`: schema, time range, per-sensor volume, gaps, speed outliers, class balance
- [ ] `src/data/pasmo.py` loader that returns a **standard row-level schema**: `ts, sensor_id, speed, type, [lat, lon]`
- [ ] `cleaning.py`: dedupe, speed bounds, timezone to UTC, outage flagging (NaN, not zero)
- [ ] `aggregate.py`: 15-min bins per sensor (`vehicles`, `peds`, `mean_speed`, `p85_speed`, class counts)
- [ ] Unit tests for aggregation (bin edges, empty bins, outages)

**Key design:** every dataset gets its own loader, but all loaders output the same standard schema. On the day, only a new loader has to be written.

**Done when:** `python -m scripts.prepare_data --dataset pasmo` produces `processed/*.parquet`.

### Phase C: Features, baseline, backtest
- [ ] `temporal.py`: hour (plus sin/cos), day of week, holiday flag (`holidays.Portugal`), lags (1, 4, 96, 672), rolling means
- [ ] Verify there is **no leakage**: features at time `t` use only data up to `t`
- [ ] `baseline.py`: seasonal naive (same time last week) and historical profile (sensor × day type × hour)
- [ ] `backtest.py`: time-based holdout (last N days), MAE per horizon, improvement vs baseline
- [ ] Notebook `02_baseline`: first backtest table

**Done when:** baseline MAE numbers exist for 15, 30 and 60 min.

### Phase D: Main models
- [ ] `boosted.py`: XGBoost direct multi-horizon (one model per horizon), `sensor` as a feature
- [ ] Try the residual target (`y − lag_week`) and compare
- [ ] Quantile models (10% and 90%) for prediction intervals
- [ ] Congestion level: sensor-and-hour percentiles to {free, dense, congested}
- [ ] Feature importance plot
- [ ] Optional: statsmodels STL / ETS as a comparison and for diagnostics (not as the main model)
- [ ] `train.py` writes `models/*.joblib` and `metrics.json` (with seed, versions, cutoff date)

**Done when:** comparison table (baseline vs XGBoost) exists for all horizons.

### Phase E: Pedestrian risk
- [ ] `risk/pedestrian.py`: transparent score from pedestrian exposure × vehicle volume × p85 speed
- [ ] Sanity check: risk should peak where pedestrians and fast traffic coincide; plot by hour
- [ ] Document the formula and its limits (no incident data, so it is a proxy and must be described that way)

### Phase F: Parking (Birmingham proxy)
- [ ] `src/data/parking.py` loader to standard schema (`ts, lot_id, capacity, occupied`)
- [ ] Occupancy rate = occupied / capacity; handle missing values and the 8:00 to 16:30 window
- [ ] Targets: `occupancy_rate` at horizon `h` and `P(full)` (occupancy at or above 95%)
- [ ] XGBoost regressor and classifier with time features and lags
- [ ] Output rows in contract format

**Note:** history is only about 11 weeks, so judge it only as "does the code work", not as model quality.

### Phase G: Prediction job and packaging
- [ ] `predict.py`: load models, build features from the latest data, write `latest.parquet` in contract format, validate the schema before writing
- [ ] `evaluate.py`: regenerate the backtest table and plots into `docs/`
- [ ] `Dockerfile` (python-slim, CPU only) and a docker-compose snippet for the scheduled job
- [ ] `run_all` command: prepare → train → evaluate → predict
- [ ] README with run instructions

**Done when:** a fresh clone plus Docker runs end to end on proxy data.

### Phase H: Integration rehearsal
- [ ] API team reads the real `latest.parquet` instead of the fake one
- [ ] Deploy to a test VM or local Docker host if the IT VM is not yet available
- [ ] Time a full retrain: it must take minutes, not hours
- [ ] Do a dry run: "new dataset arrives, how fast can we adapt?" (write a new loader, run the chain)

---

## 5. Day-1 checklist (at the hackathon)

1. Get the real files and write down: columns, time range, sampling frequency, sensor IDs, coordinates, units, timezone.
2. Write the new loader(s) into the standard schema, then run `prepare_data`.
3. Re-run exploration (gaps, outages, outliers) and update `data_dictionary.md`.
4. Re-run baseline and backtest to get real numbers.
5. Retrain and regenerate `latest.parquet`.
6. Tell the API team about any contract change **immediately**.

**Questions for the mentors**
- Exact datasets, formats, time range, update frequency: CSV only or a live API?
- How do sensors map to streets, with coordinates and segment IDs?
- Is parking occupancy per lot or per space? How long is the history?
- VM specs (RAM, CPU, disk), Docker availability, public URL with HTTPS?
- Any known incidents or events to use as validation?

---

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Real data format differs from the proxy | Loader per dataset to one standard schema; tests on the schema |
| Parking data missing or too short | Use the Birmingham-style pipeline, state limits honestly, fall back to historical profiles |
| Leakage inflates results | Time-based split only; unit test that features use no future rows |
| Percentage metrics blow up at night (near-zero counts) | Report MAE; use sMAPE only above a volume threshold |
| Sensor outages treated as zeros | Mark as NaN; exclude from targets |
| Models too slow to retrain | XGBoost on 15-min bins is fast; cap `n_estimators`, use early stopping |
| API blocked waiting for ML | Fake `latest.parquet` from day 0 |
| Scope creep (RNNs, tuning) | Stay on the ladder: baseline → XGBoost → quantiles; anything else only if time remains |

---

## 7. Model ladder (stop whenever time runs out)

| Level | Model | Role |
|---|---|---|
| 0 | Seasonal naive (same time last week) | Baseline every model must beat |
| 1 | Historical profile (sensor × day type × hour) | Dashboard weekly patterns |
| 2 | XGBoost with lags + calendar features | Main short-term forecaster |
| 3 | Quantile XGBoost | Prediction intervals for alerts |
| 4 | Optional: ETS / SARIMAX (statsmodels) | Comparison only |

---

## 8. Suggested task split (team of 4 to 5)

| Role | Prep tasks |
|---|---|
| ML lead | Phases B, C, D |
| ML / data 2 | Phases E, F, loaders |
| Backend | Data contract consumer, fake data, Docker, VM readiness |
| Mobile / dashboard | Build against the fake `latest.parquet` |
| Everyone | Phase H rehearsal, pitch story |

---

## 9. Pitch material to prepare in advance

- Backtest table: baseline vs XGBoost per horizon
- Feature importance plot ("what drives traffic")
- One scripted scenario: "Saturday 10:00, here is the route, the alerts and the parking advice"
- A short list of limits (proxy risk score, short parking history) stated honestly