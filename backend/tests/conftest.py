import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.database.init_db import init_db
from app.main import app
from app.core.security import create_access_token
from app.models.user import User, UserRole

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    init_db(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers(db_session):
    admin = db_session.query(User).filter(User.role == UserRole.ADMIN).first()
    token = create_access_token(subject=admin.id, role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def officer_headers(db_session):
    officer = db_session.query(User).filter(User.role == UserRole.OFFICER).first()
    token = create_access_token(subject=officer.id, role=officer.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def citizen_headers(db_session):
    citizen = db_session.query(User).filter(User.role == UserRole.CITIZEN).first()
    token = create_access_token(subject=citizen.id, role=citizen.role.value)
    return {"Authorization": f"Bearer {token}"}
