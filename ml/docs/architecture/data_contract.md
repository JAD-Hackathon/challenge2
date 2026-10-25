# Data Contract: ML to API (DRAFT)

`ml/scripts/predict.py` writes two Parquet files to `ml/data/predictions/`. The API only reads them.

## 1. `sensors.parquet`

| Column | Type | Description |
|---|---|---|
| `sensor_id` | string | Stable ID of a sensor or zone |
| `name` | string | Human-readable name |
| `kind` | string | ??? |
| `lat` | float | ??? |
| `lon` | float | ??? |

## 2. `forecasts.parquet`

One row per sensor, metric and target time.

| Column | Type | Description |
|---|---|---|
| `sensor_id` | string | Must exist in `sensors.parquet` |
| `metric` | string | See section 3 |
| `target_ts` | timestamp (UTC) | Time being predicted |
| `horizon_min` | int | Minutes from `generated_at` to `target_ts` |
| `value` | float | Predicted value, never null |
| `lower_80` | float | 10th percentile; null if not modelled |
| `upper_80` | float | 90th percentile; null if not modelled |
| `model_version` | string | Model identifier |
| `generated_at` | timestamp (UTC) | Time of the run |

## 3. Metrics

Only metrics named in the challenge description are listed.

| `metric` | Vertical | Unit |
|---|---|---|
| `vehicles` | Urban mobility | count per time bin |
| `speed_kmh` | Urban mobility | km/h |
| `peds` | Road safety | count per time bin |
| `parking` | Smart parking | occupancy rate or free spaces ??? |
| `footfall` | Tourism / public space | bool ??? |
| `congestion_level` | Road safety / public space | "low" / "medium", "high" ? |
| `pedestrian_risk` | Road safety / public space | rate |
| `parking_full_prob` | Urban mobility / public space | probability |

## 4. Rules

- Timestamps are UTC.
- `value` is never null. Rows that cannot be predicted are omitted, so the API must handle missing sensors or metrics.
- Each (`sensor_id`, `metric`, `target_ts`) appears once; a new run overwrites the file.
- Files are written atomically (temp file, then rename).

## 5. Changelog

| Version | Change |
|---|---|
| 0.1 | Initial draft |