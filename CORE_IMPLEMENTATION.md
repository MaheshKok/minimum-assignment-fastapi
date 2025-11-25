# Core Implementation Guide - FastAPI

> **Framework:** FastAPI 0.100+
> **Database:** PostgreSQL (async with asyncpg)
> **ORM:** SQLAlchemy 2.0 (async)
> **Pattern:** kkb_fastapi (Async Repository Pattern)
> **Python:** 3.11+

---

## 📁 Project Structure

```
app/
├── main.py                      # Application entry point
├── create_app.py                # FastAPI app factory
├── api/                         # API routers (FastAPI endpoints)
│   ├── activities.py            # Activity CRUD endpoints
│   ├── calculations.py          # Emission calculation endpoints
│   ├── factors.py               # Emission factor endpoints
│   └── reports.py               # Reporting endpoints
├── core/                        # Core functionality
│   ├── config.py                # Configuration management (TOML)
│   └── dependencies.py          # FastAPI dependency injection
├── database/                    # Database layer
│   ├── base.py                  # Engine, session configuration
│   ├── repositories/            # Data access layer
│   │   ├── base.py              # Base repository
│   │   ├── activity.py          # Activity repositories
│   │   ├── emission_factor.py   # Emission factor repository
│   │   └── emission_result.py   # Emission result repository
│   ├── schemas/                 # SQLAlchemy ORM models
│   │   ├── activity_data.py     # Activity models
│   │   ├── emission_factor.py   # Emission factor model
│   │   └── emission_result.py   # Emission result model
│   └── session_manager/         # Session management
│       ├── db_session.py        # Database context manager
│       └── exceptions.py        # Database exceptions
├── pydantic_models/             # Request/Response schemas
│   ├── activity.py              # Activity Pydantic models
│   ├── calculation.py           # Calculation request/response
│   └── emission_factor.py       # Emission factor Pydantic
├── services/                    # Business logic
│   ├── calculators/             # Emission calculators
│   │   ├── emission_calculator.py    # Main orchestrator
│   │   ├── electricity_calculator.py  # Electricity emissions
│   │   ├── travel_calculator.py       # Air travel emissions
│   │   ├── goods_services_calculator.py # Goods/services
│   │   ├── factor_matcher.py    # Fuzzy matching logic
│   │   └── unit_converter.py    # Unit conversions
│   ├── selectors/               # Data query services
│   │   └── emission_factor_selector.py
│   └── seed_database.py         # Database seeding service
├── utils/                       # Utilities
│   └── constants.py             # Constants, enums
├── cfg/                         # Configuration files
│   ├── development.toml         # Dev configuration
│   ├── test.toml                # Test configuration
│   └── production.toml          # Production configuration
├── test/                        # Tests
│   ├── conftest.py              # Pytest configuration
│   ├── factory/                 # Test factories
│   ├── test_data/               # CSV test data
│   └── unit_tests/              # Unit tests
└── workers/                     # Background workers (optional)
    └── celery_app.py.example    # Celery configuration example
```

---

## 🏗️ Architecture Layers

### Layer 1: API (FastAPI Routers)

**Location:** `app/api/`

**Purpose:** HTTP request handling, validation, authentication

**Pattern:** FastAPI router with dependency injection

**Example:**
```python
# app/api/factors.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.database.repositories import EmissionFactorRepository
from app.pydantic_models.emission_factor import (
    EmissionFactorCreate,
    EmissionFactorPydModel
)

router = APIRouter(
    prefix="/api/v1/factors",
    tags=["Emission Factors"],
)

@router.get("/", response_model=list[EmissionFactorPydModel])
async def get_factors(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session)
):
    """Get all emission factors with pagination."""
    repo = EmissionFactorRepository(session)
    factors = await repo.get_all(skip=skip, limit=limit)
    return factors

@router.post("/", response_model=EmissionFactorPydModel, status_code=201)
async def create_factor(
    data: EmissionFactorCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Create a new emission factor."""
    repo = EmissionFactorRepository(session)
    factor = await repo.create(**data.model_dump())
    await session.commit()
    return factor
```

**Key Features:**
- **Async/await:** All endpoints are async
- **Dependency injection:** Session from `Depends(get_db_session)`
- **Pydantic validation:** Automatic request/response validation
- **Type hints:** Full type safety with response_model
- **OpenAPI docs:** Auto-generated at `/docs` and `/redoc`

---

### Layer 2: Pydantic Models (Request/Response Schemas)

**Location:** `app/pydantic_models/`

**Purpose:** Input validation, serialization, API documentation

**Pattern:** Pydantic v2 models

**Example:**
```python
# app/pydantic_models/activity.py
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

class ElectricityActivityCreate(BaseModel):
    """Request schema for creating electricity activity."""

    activity_type: str = Field(..., description="Activity type")
    date: date = Field(..., description="Activity date")
    country: str = Field(..., max_length=100)
    usage_kwh: Decimal = Field(..., gt=0, description="Electricity usage in kWh")

    model_config = {
        "json_schema_extra": {
            "example": {
                "activity_type": "Electricity",
                "date": "2024-01-15",
                "country": "United Kingdom",
                "usage_kwh": 1000.5
            }
        }
    }

class ElectricityActivityPydModel(BaseModel):
    """Response schema for electricity activity."""

    id: UUID
    activity_type: str
    date: date
    country: str
    usage_kwh: Decimal
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}  # Allows ORM mode
```

**Key Features:**
- **Validation:** Automatic type and constraint validation
- **Serialization:** Convert between JSON and Python objects
- **Documentation:** Auto-generates OpenAPI schema
- **ORM mode:** `from_attributes=True` converts SQLAlchemy models

---

### Layer 3: Services (Business Logic)

**Location:** `app/services/`

**Purpose:** Business logic, calculations, orchestration

**Pattern:** Service classes with async methods

**Example:**
```python
# app/services/calculators/emission_calculator.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import EmissionResultRepository
from app.database.schemas import ElectricityActivityDBModel

class EmissionCalculationService:
    """Main orchestrator for emission calculations."""

    def __init__(self, session: AsyncSession, fuzzy_threshold: int | None = None):
        """Initialize service with database session."""
        self.session = session
        self.fuzzy_threshold = (
            fuzzy_threshold if fuzzy_threshold is not None
            else get_fuzzy_threshold_from_config()
        )
        self.electricity_calculator = ElectricityCalculator(session)
        self.goods_services_calculator = GoodsServicesCalculator(session)
        self.travel_calculator = TravelCalculator(session)

    async def calculate_single(
        self,
        activity: ActivityInstance,
        fuzzy_threshold: int | None = None,
        raise_on_error: bool = False,
    ) -> EmissionResultDBModel | None:
        """Calculate emissions for a single activity."""
        # Business logic here
        result = await self.electricity_calculator.calculate(
            activity, fuzzy_threshold=fuzzy_threshold
        )
        return result
```

**Key Features:**
- **Pure business logic:** No HTTP concerns
- **Testable:** Can be tested without FastAPI
- **Reusable:** Used by API, CLI, background jobs
- **Async:** All database operations are async

---

### Layer 4: Repositories (Data Access Layer)

**Location:** `app/database/repositories/`

**Purpose:** Database queries, CRUD operations

**Pattern:** Repository pattern with async SQLAlchemy

**Example:**
```python
# app/database/repositories/emission_factor.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.base import BaseRepository
from app.database.schemas import EmissionFactorDBModel

class EmissionFactorRepository(BaseRepository[EmissionFactorDBModel]):
    """Repository for emission factors."""

    def __init__(self, session: AsyncSession):
        super().__init__(EmissionFactorDBModel, session)

    async def get_by_type_and_region(
        self,
        activity_type: str,
        region: str
    ) -> EmissionFactorDBModel | None:
        """Get emission factor by type and region."""
        stmt = select(EmissionFactorDBModel).where(
            EmissionFactorDBModel.activity_type == activity_type,
            EmissionFactorDBModel.region == region,
            EmissionFactorDBModel.is_active == True
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all_active(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> list[EmissionFactorDBModel]:
        """Get all active emission factors with pagination."""
        stmt = (
            select(EmissionFactorDBModel)
            .where(EmissionFactorDBModel.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(EmissionFactorDBModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
```

**Key Features:**
- **Encapsulates queries:** All SQL in one place
- **Type-safe:** Generic base repository with type hints
- **Async:** Uses `await` for all queries
- **Reusable:** Common patterns in BaseRepository

---

### Layer 5: Database Schemas (ORM Models)

**Location:** `app/database/schemas/`

**Purpose:** Database table definitions

**Pattern:** SQLAlchemy 2.0 declarative models

**Example:**
```python
# app/database/schemas/emission_factor.py
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

class EmissionFactorDBModel(Base):
    """Emission factor model."""

    __tablename__ = "emission_factors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    activity_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of activity (Electricity, Air Travel, etc.)"
    )

    region = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Geographic region or country"
    )

    co2e_factor = Column(
        Numeric(precision=20, scale=10),
        nullable=False,
        comment="CO2 equivalent emission factor"
    )

    unit = Column(
        String(50),
        nullable=False,
        comment="Unit of measurement (kWh, miles, etc.)"
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index('idx_factor_type_region', 'activity_type', 'region'),
    )
```

**Key Features:**
- **PostgreSQL native:** Uses UUID, Numeric types
- **Indexes:** Performance optimization
- **Timestamps:** Automatic created_at, updated_at
- **Soft delete:** is_active flag
- **Comments:** Database-level documentation

---

## 🔄 Request Flow

### Example: Calculate Emissions

```
1. HTTP Request
   POST /api/v1/calculations/calculate
   {
     "activity_ids": ["uuid1", "uuid2"],
     "recalculate": false
   }

2. API Layer (calculations.py)
   ↓ Validates request with Pydantic
   ↓ Injects database session via Depends(get_db_session)

3. Service Layer (emission_calculator.py)
   ↓ EmissionCalculationService initialized
   ↓ Calls calculate_single() for each activity

4. Calculator Layer (electricity_calculator.py)
   ↓ ElectricityCalculator.calculate()
   ↓ Uses FactorMatcher for fuzzy matching

5. Repository Layer (emission_factor.py, emission_result.py)
   ↓ Queries emission factors from database
   ↓ Creates emission result record

6. Database Layer
   ↓ PostgreSQL async queries via asyncpg
   ↓ Returns results

7. Response
   ← Pydantic serializes to JSON
   ← Returns EmissionResultPydModel[]
```

---

## 🗄️ Database Configuration

### Session Management

**Pattern:** Async context manager

```python
# app/database/session_manager/db_session.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

class Database:
    """Database session manager."""

    _engine = None
    _session_factory = None

    @classmethod
    def init(cls, db_url: str, engine_kw: dict):
        """Initialize engine and session factory."""
        cls._engine = create_async_engine(db_url, **engine_kw)
        cls._session_factory = sessionmaker(
            cls._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def __aenter__(self) -> AsyncSession:
        """Create and return session."""
        if self._session_factory is None:
            raise RuntimeError("Database not initialized")
        self.session = self._session_factory()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session."""
        await self.session.close()
```

### Usage in Dependencies

```python
# app/core/dependencies.py
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session_manager.db_session import Database

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database session."""
    async with Database() as session:
        yield session
```

### Engine Configuration

```python
# app/database/base.py
engine_kw = {
    "pool_pre_ping": True,        # Check connection before use
    "pool_size": 2,                # Connections to keep open
    "max_overflow": 4,             # Extra connections allowed
    "connect_args": {
        "prepared_statement_cache_size": 0,  # Disable for async
        "statement_cache_size": 0,
    },
}
```

**Key Features:**
- **Connection pooling:** QueuePool with size 2, overflow 4
- **Pool pre-ping:** Validates connections before use
- **Async:** Full async/await support
- **Context manager:** Automatic session cleanup

---

## ⚙️ Configuration Management

### TOML Configuration

**Files:** `app/cfg/{development,test,production}.toml`

```toml
# app/cfg/development.toml
ENVIRONMENT = "development"

[db]
host = "localhost"
port = "5432"
database = "minimum_emissions_dev"
username = "postgres"
password = "postgres"

[logging]
version = 1
disable_existing_loggers = false

[logging.root]
level = "DEBUG"
handlers = ["console"]

[api]
title = "Carbon Emissions Calculator API"
version = "1.0.0"
debug = true

[emission_calculation]
fuzzy_match_threshold = 80
default_confidence_score = 1.0
decimal_precision = 4
```

### Loading Configuration

```python
# app/core/config.py
import tomli as toml
from pathlib import Path

class Config:
    """Configuration loader."""

    def __init__(self, path: Path):
        self.path = path
        self.data = self.load_path(path)

    @classmethod
    def load_path(cls, path: Path) -> dict:
        """Load TOML from file."""
        text = path.read_text()
        return toml.loads(text)

    def update(self, data, sep="_"):
        """Update from environment variables."""
        # Allows DB_HOST to override db.host
        pass

def get_config(config_file: str = "development.toml") -> Config:
    """Get configuration instance."""
    config_path = Path(__file__).parent.parent / "cfg" / config_file
    return Config(config_path).update(os.environ)
```

---

## 🚀 Application Lifecycle

### Startup (Lifespan)

```python
# app/create_app.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logging.info("Application startup")
    async_db_url = get_db_url(app.state.config)
    Database.init(async_db_url, engine_kw=engine_kw)
    logging.info("Database initialized")

    try:
        yield  # Application runs
    finally:
        # Shutdown
        logging.info("Application shutdown")
        # Cleanup if needed

def get_app(config_file: str) -> FastAPI:
    """Application factory."""
    config = get_config(config_file)

    app = FastAPI(
        title=config.data.get("api", {}).get("title"),
        version=config.data.get("api", {}).get("version"),
        lifespan=lifespan,
    )

    app.state.config = config  # Store config in app state
    register_routers(app)

    return app
```

### Running the App

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 🧪 Testing

### Test Configuration

```python
# app/test/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_session():
    """Provide database session for tests."""
    engine = create_async_engine("postgresql+asyncpg://...")
    async_session = sessionmaker(engine, class_=AsyncSession)

    async with async_session() as session:
        yield session

    await engine.dispose()
```

### Test Example

```python
# app/test/unit_tests/test_services/test_calculators.py
import pytest
from app.services.calculators.emission_calculator import EmissionCalculationService

@pytest.mark.asyncio
async def test_calculate_single(db_session):
    """Test single emission calculation."""
    service = EmissionCalculationService(db_session)

    activity = await create_electricity_activity(db_session)
    result = await service.calculate_single(activity)

    assert result is not None
    assert result.co2e_tonnes > 0
```

---

## 📊 Key Differences from Django

| Aspect | Django | FastAPI |
|--------|--------|---------|
| **Framework** | Synchronous | Async/await |
| **ORM** | Django ORM | SQLAlchemy 2.0 |
| **Validation** | Django Forms/Serializers | Pydantic models |
| **Routing** | URL patterns | APIRouter decorators |
| **Dependency Injection** | Manual | Built-in with Depends() |
| **API Docs** | Manual (DRF) | Auto-generated OpenAPI |
| **Session** | Per-request automatic | Manual with context manager |
| **Database** | Sync queries | Async queries with await |
| **Configuration** | settings.py | TOML files |
| **Migrations** | Django migrations | Alembic |

---

## 🎯 Best Practices

### 1. Always Use Async/Await

```python
# ❌ Wrong
def get_factors(session):
    return session.query(EmissionFactor).all()

# ✅ Correct
async def get_factors(session: AsyncSession):
    result = await session.execute(select(EmissionFactor))
    return result.scalars().all()
```

### 2. Use Dependency Injection

```python
# ❌ Wrong
@router.get("/factors")
async def get_factors():
    session = Database().get_session()  # Manual
    ...

# ✅ Correct
@router.get("/factors")
async def get_factors(session: AsyncSession = Depends(get_db_session)):
    ...  # FastAPI handles session lifecycle
```

### 3. Separate Pydantic from SQLAlchemy

```python
# ❌ Wrong - mixing concerns
class EmissionFactor(Base, BaseModel):  # Don't do this
    ...

# ✅ Correct - separate models
class EmissionFactorDBModel(Base):  # SQLAlchemy
    ...

class EmissionFactorPydModel(BaseModel):  # Pydantic
    ...
```

### 4. Use Type Hints Everywhere

```python
# ❌ Wrong
async def get_factor(id):
    ...

# ✅ Correct
async def get_factor(id: UUID) -> EmissionFactorDBModel | None:
    ...
```

### 5. Commit Explicitly

```python
# ❌ Wrong - no commit
async def create_factor(session, data):
    factor = EmissionFactor(**data)
    session.add(factor)
    return factor  # Not saved!

# ✅ Correct
async def create_factor(session, data):
    factor = EmissionFactor(**data)
    session.add(factor)
    await session.commit()  # Explicitly commit
    return factor
```

---

## 📚 Additional Resources

- **FastAPI Docs:** https://fastapi.tiangolo.com
- **SQLAlchemy 2.0:** https://docs.sqlalchemy.org/en/20/
- **Pydantic V2:** https://docs.pydantic.dev/latest/
- **Asyncpg:** https://magicstack.github.io/asyncpg/

---

## 🔍 Common Issues

### Issue: Session not committed

**Symptom:** Changes not persisted to database

**Solution:**
```python
async def create_factor(session: AsyncSession, data):
    factor = EmissionFactorDBModel(**data)
    session.add(factor)
    await session.commit()  # Don't forget!
    await session.refresh(factor)  # Reload from DB
    return factor
```

### Issue: "greenlet_spawn" error

**Symptom:** `greenlet_spawn has not been called`

**Solution:** Always use `await` with async operations:
```python
# ❌ Wrong
result = session.execute(select(Model))

# ✅ Correct
result = await session.execute(select(Model))
```

### Issue: Session closed prematurely

**Symptom:** `This session is closed`

**Solution:** Use dependency injection or context manager properly:
```python
# ✅ Correct
async with Database() as session:
    factor = await repo.get_by_id(id)
    # Session still open here
    return factor
# Session closed here
```

---

## 🎉 Summary

This FastAPI project follows these key patterns:

1. **Async/Await:** All database operations are async
2. **Repository Pattern:** Data access layer abstraction
3. **Dependency Injection:** FastAPI's Depends() for session management
4. **Pydantic Validation:** Type-safe request/response handling
5. **Service Layer:** Business logic separated from HTTP
6. **TOML Configuration:** Environment-specific settings
7. **SQLAlchemy 2.0:** Modern async ORM
8. **Type Safety:** Full type hints throughout

**The architecture is clean, testable, and scalable.**
