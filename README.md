# Carbon Emissions Calculator - FastAPI

A high-performance carbon emissions calculation engine built with FastAPI, converted from Django following kkb_fastapi patterns.

## 🎯 Features

- **CO2e Emissions Calculation**: Calculate emissions from electricity usage, air travel, and purchased goods & services
- **Fuzzy Matching**: Intelligent emission factor matching with confidence scoring
- **PostgreSQL + Async**: High-performance async database operations
- **RESTful API**: Comprehensive API with automatic documentation
- **Type Safety**: Full Pydantic validation
- **Production Ready**: Following enterprise patterns from kkb_fastapi

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 12+
- pip

### Installation

```bash
# Clone or navigate to project
cd /Users/maheshkokare/PycharmProjects/minimum-assignment-fastapi

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Mac/Linux
# Or on Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Database Setup

```bash
# Create PostgreSQL databases
createdb minimum_emissions_dev
createdb minimum_emissions_test

# Update configuration
# Edit app/cfg/development.toml with your database credentials
```

### Run Migrations

```bash
# Initialize Alembic (first time only)
alembic init alembic_migrations

# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

### Start the Server

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --port 8000

# Or run directly
python -m app.main
```

### Access the API

- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 📚 Documentation

- **[Core Implementation Guide](docs/CORE_IMPLEMENTATION.md)**: Comprehensive architecture and conversion documentation
- **API Documentation**: Available at `/docs` endpoint when running
- **Original Assignment**: See `/docs/ASSIGNMENT.md` (from Django project)

## 🏗️ Project Structure

```
minimum-assignment-fastapi/
├── app/
│   ├── api/                    # FastAPI routers
│   ├── cfg/                    # TOML configuration files
│   ├── core/                   # Core modules (config, dependencies)
│   ├── database/               # SQLAlchemy models & session management
│   ├── pydantic_models/        # API request/response models
│   ├── services/               # Business logic layer
│   ├── utils/                  # Utilities
│   ├── create_app.py           # FastAPI app factory
│   └── main.py                 # Application entry point
├── alembic_migrations/         # Database migrations
├── docs/                       # Documentation
├── tests/                      # Test suite
└── requirements.txt            # Dependencies
```

## 🔌 API Endpoints

### Emission Factors
```
GET    /api/v1/factors          # List all emission factors
POST   /api/v1/factors          # Create emission factor
GET    /api/v1/factors/{id}     # Get specific factor
PUT    /api/v1/factors/{id}     # Update factor
DELETE /api/v1/factors/{id}     # Delete factor
```

### Activity Data
```
GET  /api/v1/activities/electricity      # List electricity activities
POST /api/v1/activities/electricity      # Create electricity activity

GET  /api/v1/activities/air-travel       # List air travel activities
POST /api/v1/activities/air-travel       # Create air travel activity

GET  /api/v1/activities/goods-services   # List goods & services
POST /api/v1/activities/goods-services   # Create goods & services activity
```

### Calculations
```
POST /api/v1/calculations/calculate      # Calculate emissions
```

### Reports
```
GET /api/v1/reports/emissions            # Generate emissions report
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit_tests/test_calculators.py
```

## ⚙️ Configuration

Configuration is managed via TOML files in `app/cfg/`:

- `development.toml` - Development environment
- `production.toml` - Production environment
- `test.toml` - Test environment

Example configuration:

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

## 📊 Data Models

### Emission Factor
Stores CO2e emission factors for different activities.

### Activity Data
Three types:
- **Electricity Activity**: Scope 2 emissions from electricity consumption
- **Air Travel Activity**: Scope 3, Category 6 emissions from business travel
- **Goods & Services Activity**: Scope 3, Category 1 emissions from purchases

### Emission Result
Links activities to emission factors with calculated CO2e emissions.

## 🔄 Conversion from Django

This project was converted from Django REST Framework to FastAPI following patterns from kkb_fastapi:

| Django/DRF | FastAPI |
|------------|---------|
| Django ORM | SQLAlchemy async |
| DRF Serializers | Pydantic models |
| ViewSets | Router functions |
| settings.py | TOML configuration |
| SQLite | PostgreSQL + asyncpg |
| Synchronous | Asynchronous |

See [CORE_IMPLEMENTATION.md](docs/CORE_IMPLEMENTATION.md) for detailed conversion documentation.

## 🛠️ Technology Stack

- **Framework**: FastAPI 0.109.1
- **Database**: PostgreSQL with asyncpg
- **ORM**: SQLAlchemy 2.0 (async)
- **Validation**: Pydantic v2
- **Testing**: pytest + pytest-asyncio
- **Migrations**: Alembic
- **Server**: Uvicorn
- **Fuzzy Matching**: rapidfuzz

## 📝 Development

### Code Structure

Following kkb_fastapi patterns:
- **Separation of Concerns**: Database models, Pydantic models, routers, and services are clearly separated
- **Dependency Injection**: Database sessions injected via FastAPI's Depends
- **Async/Await**: Full async support throughout
- **Type Safety**: Comprehensive type hints with Pydantic

### Adding New Endpoints

1. Create Pydantic models in `app/pydantic_models/`
2. Create SQLAlchemy model in `app/database/schemas/`
3. Create router in `app/api/`
4. Register router in `app/create_app.py`
5. Create tests in `tests/unit_tests/`

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 🤝 Contributing

This project follows the patterns established in kkb_fastapi. When contributing:

1. Maintain async/await patterns
2. Use Pydantic for validation
3. Follow SQLAlchemy async patterns
4. Write tests with pytest-asyncio
5. Update documentation

## 📄 License

[Add your license here]

## 🙏 Acknowledgments

- **Django Original**: Converted from Django-based carbon calculator
- **kkb_fastapi**: Reference project for FastAPI patterns
- **Claude Code**: AI-assisted development with Hive Mind collective intelligence

## 📞 Support

For issues and questions:
- Check [CORE_IMPLEMENTATION.md](docs/CORE_IMPLEMENTATION.md)
- Review API docs at `/docs`
- Check original Django project documentation

---

**Version**: 1.0.0
**Converted**: November 2025
**Status**: Production Ready (pending emission calculator completion)
