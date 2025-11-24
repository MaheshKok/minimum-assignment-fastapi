# CORE IMPLEMENTATION - FastAPI Carbon Emissions Calculator

**Converted from Django to FastAPI following kkb_fastapi patterns**

## 🎯 Project Overview

This is a FastAPI-based carbon emissions calculation engine converted from Django REST Framework. It calculates CO2e emissions from activity data (electricity usage, air travel, purchased goods & services) using emission factors.

## 📊 Architecture Overview

### Key Design Patterns (from kkb_fastapi)

1. **TOML Configuration**: Environment-based config files (`app/cfg/`)
2. **Database Session Manager**: Async context manager pattern for PostgreSQL
3. **Separation of Concerns**: SQLAlchemy models vs Pydantic models
4. **Dependency Injection**: FastAPI's Depends for database sessions
5. **Service Layer**: Business logic separated from API layer
6. **Async/Await**: Full async support throughout the stack

## 🏗️ Project Structure

```
minimum-assignment-fastapi/
├── app/
│   ├── __init__.py
│   ├── main.py                    # Application entry point
│   ├── create_app.py              # FastAPI app factory
│   │
│   ├── cfg/                       # TOML configuration files
│   │   ├── development.toml       # Development settings
│   │   ├── production.toml        # Production settings
│   │   └── test.toml             # Test settings
│   │
│   ├── core/                      # Core application modules
│   │   ├── config.py             # Configuration loader
│   │   └── dependencies.py        # FastAPI dependencies
│   │
│   ├── database/                  # Database layer
│   │   ├── __init__.py           # Base declarative
│   │   ├── base.py               # Database engine & URL setup
│   │   ├── schemas/              # SQLAlchemy models
│   │   │   ├── emission_factor.py
│   │   │   ├── activity_data.py
│   │   │   └── emission_result.py
│   │   └── session_manager/      # Session management
│   │       ├── db_session.py     # Database context manager
│   │       └── exceptions.py
│   │
│   ├── pydantic_models/          # API request/response models
│   │   ├── emission_factor.py
│   │   ├── activity.py
│   │   └── calculation.py
│   │
│   ├── api/                      # FastAPI routers
│   │   ├── __init__.py
│   │   ├── factors.py           # Emission factors CRUD
│   │   ├── activities.py        # Activity data CRUD
│   │   ├── calculations.py      # Emission calculations
│   │   └── reports.py           # Report generation
│   │
│   ├── services/                 # Business logic layer
│   │   ├── calculators/
│   │   │   ├── unit_converter.py    # Unit conversions
│   │   │   ├── factor_matcher.py    # Fuzzy matching
│   │   │   └── emission_calculator.py
│   │   └── selectors/               # Database queries
│   │
│   ├── utils/                    # Utility modules
│   │   └── constants.py         # Application constants
│   │
│   └── test/                     # Test suite
│       ├── conftest.py          # Pytest fixtures
│       ├── factory/             # Test factories
│       └── unit_tests/
│
├── alembic_migrations/          # Database migrations
│   └── versions/
│
├── tests/                       # Test data
│   └── test_data/              # CSV test files
│
├── docs/                        # Documentation
│   └── CORE_IMPLEMENTATION.md   # This file
│
├── requirements.txt             # Python dependencies
├── alembic.ini                 # Alembic configuration
├── .gitignore
└── README.md
```

## 🔄 Django to FastAPI Conversion Mapping

### Models (Django ORM → SQLAlchemy)

**Django Pattern:**
```python
from django.db import models

class EmissionFactor(TimeStampedModel):
    activity_type = models.CharField(max_length=100)
    co2e_factor = models.DecimalField(max_digits=10, decimal_places=6)
```

**FastAPI Pattern:**
```python
from sqlalchemy import Column, String, Numeric, UUID
from app.database import Base

class EmissionFactorDBModel(Base):
    __tablename__ = "emission_factors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_type = Column(String(100), nullable=False)
    co2e_factor = Column(Numeric(10, 6), nullable=False)
```

**Key Changes:**
- Django's `models.Model` → SQLAlchemy's `Base`
- UUID primary keys instead of auto-incrementing integers
- Explicit table naming with `__tablename__`
- Timestamps managed in mixin (created_at, updated_at)

### Serializers (DRF → Pydantic)

**Django Pattern:**
```python
from rest_framework import serializers

class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = '__all__'
```

**FastAPI Pattern:**
```python
from pydantic import BaseModel, Field, ConfigDict

class EmissionFactorPydModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_type: str = Field(..., max_length=100)
    co2e_factor: Decimal
```

**Key Changes:**
- DRF Serializers → Pydantic Models
- `from_attributes=True` for ORM compatibility
- Type hints for validation
- Separate Create/Update/Response models

### ViewSets (DRF → FastAPI Routers)

**Django Pattern:**
```python
from rest_framework import viewsets

class EmissionFactorViewSet(viewsets.ModelViewSet):
    queryset = EmissionFactor.objects.all()
    serializer_class = EmissionFactorSerializer
```

**FastAPI Pattern:**
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/factors", tags=["Emission Factors"])

@router.get("/", response_model=List[EmissionFactorPydModel])
async def list_emission_factors(
    session: AsyncSession = Depends(get_db_session)
):
    stmt = select(EmissionFactorDBModel)
    result = await session.execute(stmt)
    return result.scalars().all()
```

**Key Changes:**
- ViewSets → Router functions
- Explicit async/await
- Dependency injection for database sessions
- Path operations for CRUD

## 🗄️ Database Architecture

### PostgreSQL Setup

Following kkb_fastapi pattern for PostgreSQL with asyncpg:

```python
# Database URL format
postgresql+asyncpg://username:password@host:port/database

# Connection pooling
engine_kw = {
    "pool_pre_ping": True,
    "pool_size": 2,
    "max_overflow": 4,
}
```

### Session Management

**Context Manager Pattern:**
```python
async with Database() as session:
    # Session automatically committed/rolled back
    result = await session.execute(select(Model))
    items = result.scalars().all()
```

**Dependency Injection:**
```python
@router.get("/items")
async def get_items(session: AsyncSession = Depends(get_db_session)):
    # Session provided by FastAPI dependency injection
    result = await session.execute(select(Item))
    return result.scalars().all()
```

## 📐 Data Models

### Emission Factor

Stores CO2e emission factors for different activities:

```python
{
    "id": "uuid",
    "activity_type": "Electricity" | "Air Travel" | "Purchased Goods and Services",
    "lookup_identifier": "United Kingdom",  # Matching key
    "unit": "kWh" | "kilometres" | "GBP",
    "co2e_factor": 0.193,  # kgCO2e per unit
    "scope": 1 | 2 | 3,
    "category": 1 | 6 | null,
    "source": "DEFRA 2024",
    "created_at": "timestamp",
    "updated_at": "timestamp"
}
```

### Activity Data

Three types of activities:

**1. Electricity Activity (Scope 2)**
```python
{
    "id": "uuid",
    "date": "2024-01-15",
    "activity_type": "Electricity",
    "country": "United Kingdom",
    "usage_kwh": 1000.0,
    "source_file": "Electricity.csv",
    "raw_data": {}  # Original CSV row
}
```

**2. Air Travel Activity (Scope 3, Category 6)**
```python
{
    "id": "uuid",
    "date": "2024-01-15",
    "activity_type": "Air Travel",
    "distance_miles": 3459.0,
    "distance_km": 5568.51,  # Auto-calculated
    "flight_range": "Long-haul",
    "passenger_class": "Business class",
    "source_file": "Air_Travel.csv",
    "raw_data": {}
}
```

**3. Goods & Services Activity (Scope 3, Category 1)**
```python
{
    "id": "uuid",
    "date": "2024-01-15",
    "activity_type": "Purchased Goods and Services",
    "supplier_category": "Wholesale trade, except of motor vehicles...",
    "spend_gbp": 1500.00,
    "description": "Additional details",
    "source_file": "Purchased_Goods_and_Services.csv",
    "raw_data": {}
}
```

### Emission Result

Calculated emissions linking activities to factors:

```python
{
    "id": "uuid",
    "activity_type": "Electricity",
    "activity_id": "uuid",  # Reference to activity
    "emission_factor_id": "uuid",  # Factor used
    "co2e_tonnes": 0.193,  # Calculated emissions
    "confidence_score": 1.0,  # Matching confidence (0.0-1.0)
    "calculation_metadata": {
        "method": "direct_multiplication",
        "matched_via": "exact_match"
    },
    "calculation_date": "2024-01-15",
    "created_at": "timestamp"
}
```

## 🧮 Calculation Logic

### 1. Unit Converter Service

Handles unit conversions:
- Miles ↔ Kilometres (1 mile = 1.60934 km)
- Tonnes ↔ Kilograms (1 tonne = 1000 kg)
- Number normalization (handles commas in CSV data)

```python
from app.services.calculators.unit_converter import UnitConverter

km = UnitConverter.miles_to_km(3459)  # → 5568.51 km
```

### 2. Factor Matcher Service

Matches activity data to emission factors:

**Exact Matching:**
```python
factor = await matcher.exact_match("Electricity", "United Kingdom")
```

**Fuzzy Matching:**
```python
# Handles "Business Class" vs "Business class"
factor, confidence = await matcher.fuzzy_match(
    "Air Travel",
    "Long-haul, Business class",
    threshold=80  # 80% similarity
)
```

**Air Travel (Two-Column Lookup):**
```python
factor, confidence = await matcher.match_air_travel(
    flight_range="Long-haul",
    passenger_class="Business class"
)
```

### 3. Emission Calculator

Calculates CO2e emissions:

**Formula:**
```
CO2e (tonnes) = Activity Amount × Emission Factor ÷ 1000
```

**Example - Electricity:**
```
1000 kWh × 0.193 kgCO2e/kWh ÷ 1000 = 0.193 tonnes CO2e
```

**Example - Air Travel:**
```
1. Convert: 3459 miles × 1.60934 = 5568.51 km
2. Match factor: "Long-haul, Business class" → 0.04696 kgCO2e/km
3. Calculate: 5568.51 km × 0.04696 ÷ 1000 = 261.52 tonnes CO2e
```

## 🔌 API Endpoints

### Emission Factors

```
GET    /api/v1/factors               # List factors
GET    /api/v1/factors/{id}          # Get factor
POST   /api/v1/factors               # Create factor
PUT    /api/v1/factors/{id}          # Update factor
DELETE /api/v1/factors/{id}          # Delete factor
```

### Activities

```
GET  /api/v1/activities/electricity      # List electricity activities
POST /api/v1/activities/electricity      # Create electricity activity

GET  /api/v1/activities/air-travel       # List air travel activities
POST /api/v1/activities/air-travel       # Create air travel activity

GET  /api/v1/activities/goods-services   # List goods & services activities
POST /api/v1/activities/goods-services   # Create goods & services activity
```

### Calculations

```
POST /api/v1/calculations/calculate      # Calculate emissions for activities
```

### Reports

```
GET /api/v1/reports/emissions            # Generate comprehensive report
```

## ⚙️ Configuration

### TOML Configuration Files

**app/cfg/development.toml:**
```toml
ENVIRONMENT = "development"

[db]
host = "localhost"
port = "5432"
database = "minimum_emissions_dev"
username = "postgres"
password = "postgres"

[api]
title = "Carbon Emissions Calculator API"
version = "1.0.0"
debug = true

[emission_calculation]
fuzzy_match_threshold = 0.8
decimal_precision = 4
```

### Environment-Specific Settings

- **Development**: Full debugging, verbose logging
- **Production**: Optimized, minimal logging
- **Test**: Isolated test database

## 🧪 Testing Strategy

### Test Structure (following kkb_fastapi)

```python
# conftest.py
@pytest.fixture(scope="function")
async def test_async_engine(test_config):
    await create_database(test_config)
    async_db_url = get_db_url(test_config)
    engine = create_async_engine(async_db_url, ...)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="function", autouse=True)
async def db_cleanup(test_async_engine):
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
```

### Factory Pattern

```python
# factory/emission_factor.py
class EmissionFactorFactory(BaseFactory):
    class Meta:
        model = EmissionFactorDBModel

    activity_type = "Electricity"
    lookup_identifier = "United Kingdom"
    co2e_factor = Decimal("0.193")
```

## 🚀 Running the Application

### 1. Setup Environment

```bash
cd /Users/maheshkokare/PycharmProjects/minimum-assignment-fastapi

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Database

```bash
# Create PostgreSQL database
createdb minimum_emissions_dev

# Update app/cfg/development.toml with your database credentials
```

### 3. Run Migrations

```bash
# Initialize Alembic (if not done)
alembic init alembic_migrations

# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

### 4. Start Application

```bash
# Development
python -m app.main

# Or with uvicorn directly
uvicorn app.main:app --reload --port 8000
```

### 5. Access API

- API Documentation: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## 📝 Key Differences: Django vs FastAPI

| Aspect | Django/DRF | FastAPI |
|--------|-----------|---------|
| **Models** | Django ORM | SQLAlchemy + Pydantic |
| **Queries** | Sync QuerySets | Async SQLAlchemy |
| **Serialization** | DRF Serializers | Pydantic Models |
| **Views** | ViewSets/APIViews | Router Functions |
| **Validation** | Serializer validation | Pydantic validation |
| **Dependencies** | Middleware/Mixins | Depends() |
| **Testing** | Django TestCase | pytest-asyncio |
| **Database** | SQLite (default) | PostgreSQL + asyncpg |
| **Performance** | Synchronous | Asynchronous |
| **Config** | settings.py | TOML files |

## 🎯 Migration Checklist

- [x] TOML configuration system
- [x] PostgreSQL with asyncpg
- [x] SQLAlchemy async models
- [x] Pydantic request/response models
- [x] FastAPI routers with dependency injection
- [x] Async service layer
- [x] Unit converter service
- [x] Factor matcher service (async)
- [x] Database session manager
- [x] Application factory pattern
- [x] Health check endpoints
- [ ] Complete emission calculator service
- [ ] Alembic migrations
- [ ] pytest-asyncio test suite
- [ ] Data seeding scripts
- [ ] Report generation

## 🔗 References

- **kkb_fastapi**: Reference FastAPI project for patterns
- **Django Project**: `/Users/maheshkokare/PycharmProjects/minimum-assignment`
- **FastAPI Project**: `/Users/maheshkokare/PycharmProjects/minimum-assignment-fastapi`

## 📚 Further Reading

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Pydantic V2](https://docs.pydantic.dev/latest/)
- [Alembic Migrations](https://alembic.sqlalchemy.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)

---

**Converted by**: Claude Code with Hive Mind collective intelligence
**Date**: November 24, 2025
**Version**: 1.0.0
