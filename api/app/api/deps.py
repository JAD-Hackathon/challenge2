from typing import Annotated

from app.database import get_db
from fastapi import Depends
from sqlalchemy.orm import Session

SessionDep = Annotated[Session, Depends(get_db)]
