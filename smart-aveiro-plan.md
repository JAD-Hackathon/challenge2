# Smart Aveiro — Team Plan

> Hackathon Aveiro Tech City, Challenge #1: _"Smart Aveiro: From Data to Action"_
> Goal: turn Living Lab sensor data into **actionable** output, combining **at least 2 of 4 verticals**, and deploy it on the IT VMs.

---

## 1. Concept

**Focus: the driver.**

A driver-facing service that uses the city's sensor data to answer three questions:

- _Where should I go?_ Route and parking recommendations.
- _What's ahead of me?_ Congestion, busy crosswalks and crowded zones.
- _When should I go?_ Short-term forecasts.

### Verticals and how they serve the driver

| Vertical                                   | Driver use                      | Actionable output                                               |
| :----------------------------------------- | :------------------------------ | :-------------------------------------------------------------- |
| Urban Mobility (counts, typology, speeds)  | Congestion forecast per segment | "Avoid Av. Lourenço Peixinho, slow in 20 min." Route weighting. |
| Smart Parking (occupancy)                  | Parking availability prediction | "Park X will be full by 10:30. Go to Park Y (4 min away)."      |
| Road Safety (crosswalk usage, pedestrians) | Pedestrian risk on the route    | Voice alert: "High pedestrian activity at the next crosswalk."  |
| Tourism & Public Space (footfall, density) | Crowded zones and events        | Avoid crowded areas. Suggest parking at the edge of busy zones. |

The strongest cross-vertical combination is **Parking + Mobility + Road Safety**. Tourism can be added as an extra signal.

---

## 2. Open Questions

### Product

- [ ] **Mobile app: Waze-like, a dashboard, or both?**
    - Proposal: two modes.
        - **Drive mode:** map, route and voice alerts only. No interaction while driving.
        - **Explore mode:** clickable zones on the map that show model data (forecasts, occupancy, risk).
- [ ] **Dashboard audience:** tourists or citizens (the "tourist info office" idea), or municipal operators? The two audiences need very different screens.
- [ ] **Forecast horizon "next x weeks":** is it realistic? That depends on how much history exists.
    - Weeks ahead only allows _patterns_ (day-of-week and hour profiles, seasonality).
    - Accurate predictions are only realistic for the short term (15 min to a few hours).
    - Proposal: short-term forecasts in the app, weekly patterns in the dashboard.
- [ ] **How much "Waze" do we build?** Full turn-by-turn navigation (rerouting, map matching) is too heavy for a hackathon.
    - Proposal for the MVP: compute a route, show it, give alerts along it, and recalculate on demand.

### Technical

- [ ] Is a separate **Laravel** backend needed, or can the dashboard consume the **FastAPI** directly? One fewer backend means less integration work.
- [ ] VM specs: RAM, CPU and disk. OSRM, Photon and tiles all need resources.
- [ ] Do the VMs have Docker and public access (domain, HTTPS)?

---

---

## 3. Stack

| Layer             | Tech                                                |
| :---------------- | :-------------------------------------------------- |
| Dashboard         | PHP, Laravel (+ Leaflet or MapLibre GL JS for maps) |
| API               | Python, FastAPI                                     |
| Mobile App        | Dart, Flutter                                       |
| Data Science & ML | Python: pandas, etc...                              |
| Routing / Geo     | OSRM, GraphHopper or Valhalla, plus Photon          |
| Deploy            | Docker, docker-compose on the IT VMs                |

### Mobile App dependencies (free for commercial use)

- **map:** `flutter_map` or `maplibre_gl` (both open source)
- **tiles:** OpenFreeMap (free hosted) or self-hosted Protomaps (PMTiles)
- **GPS:** `geolocator`
- **routes:** OSRM, GraphHopper or Valhalla (self-hosted, Portugal or Aveiro extract)
- **geocoding:** Photon or Nominatim (self-hosted)
- **geometry/distances:** `latlong2`
- **voice:** `flutter_tts`
- **attribution:** "© OpenStreetMap contributors" visible on the map (required by ODbL)

### Dashboard dependencies (free for commercial use)

### Data dependencies (free for commercial use)

---

## 4. Architecture

```
            ┌────────────────────┐
            │  Living Lab data   │  (CSV)
            └─────────┬──────────┘
                      ▼
            ┌────────────────────┐
            │  ML pipeline (Py)  │  ingest → clean → <something idk :D> → predict
            └─────────┬──────────┘
                      ▼
┌──────────┐  ┌────────────────┐  ┌──────────────┐
│ OSRM     │◄─┤ FastAPI        ├─►│ Photon       │
│ (routes) │  │ /zones /predict│  │ (geocoding)  │
└──────────┘  │ /route /alerts │  └──────────────┘
              └───┬────────┬───┘
                  ▼        ▼
          ┌──────────┐  ┌──────────┐
          │ Laravel  │  │ Flutter  │
          │ Dashboard│  │ App      │
          └──────────┘  └──────────┘
```

All services run in a single `docker-compose.yml` on the IT VM.

---

## 5. Data & ML Pipeline

---

## 6. API Draft (FastAPI)

| Method | Endpoint                      | Returns                                  |
| :----- | :---------------------------- | :--------------------------------------- |
| GET    | `/zones`                      | Zone polygons + current status           |
| GET    | `/zones/{id}/forecast?hours=` | Forecasts for the zone                   |
| GET    | `/parking?lat=&lon=&eta=`     | Parks ranked by predicted availability   |
| GET    | `/route?from=&to=`            | OSRM route + alerts along it             |
| GET    | `/alerts?bbox=`               | Active alerts (risk, congestion, crowds) |
| GET    | `/patterns/{zone}`            | Weekly pattern (dashboard)               |

---

## 7. Possible Data

- ??????

## 8. Risks

- **The dashboard trap:** every screen must answer _"what should I do?"_, not just _"what happened?"_.
- **Scope creep in the app:** no full navigation engine. Route + alerts is enough for the demo.
- **Data quality:** confirm access with the mentors **on day 1** before building models.
- **Deployment:** containerise from hour one, and test on the VM early.
