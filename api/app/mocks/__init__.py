"""Mock mode (API_MOCK=true): the same routes and schemas as app/api/v1, but the database is
replaced by an in-memory catalogue, so the web can work without PostGIS.

Uploads still go to the ML service, which has its own mock (ML_MOCK=true): the API doesn't
fake ML, it only fakes the database.

    router.py        mock /v1 router, swapped in by app/api/router.py
    endpoints/       mirror of app/api/v1/endpoints (same paths, params, schemas, docs)
    services/        what each mock endpoint does (stands in for app/services)
    store.py         in-memory catalogue, reset to the seed on every start
    placeholders.py  draws the seed images into the shared folder
    fixtures/        seed data (Aveiro)

Seed images are written to the shared folder like ML's (SHARED_DIR/images/<image_id>.jpg) and
served by the same /media route, so image URLs work the same way in both modes.
"""


def setup_mock_data() -> None:
    from app.mocks.store import store

    store.reset()
