"""SampleItems CRUD router — wired via `create_crud_router`.

Provides: GET /api/sample-items, GET /api/sample-items/{id},
          POST /api/sample-items, PATCH /api/sample-items/{id},
          DELETE /api/sample-items/{id}

To add auth, pass `current_user_dep=get_current_user` from whichever auth
prefab is installed (auth-oauth2, auth-session, etc.).
"""

from app.crud.router_factory import create_crud_router
from app.models.sample_item import SampleItem, SampleItemCreate, SampleItemUpdate

sample_items_router = create_crud_router(
    model_class=SampleItem,
    create_schema=SampleItemCreate,
    update_schema=SampleItemUpdate,
    prefix="/api/sample-items",
    tag="sample-items",
    # current_user_dep=get_current_user,  # uncomment after adding an auth prefab
)
