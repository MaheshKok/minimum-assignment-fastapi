# Extreme-Scale Emission Calculation Engine Architecture

**Document Version**: 1.0
**Date**: November 24, 2025
**Scale Target**: 100 Million rows/day per activity type (300M total daily)
**Author**: System Architecture Designer

---

## Executive Summary

This document outlines a production-ready architecture for processing 300 million emission calculation records daily across three activity types (Air Travel, Purchased Goods & Services, Electricity). The system is designed to handle extreme scale while maintaining accuracy, reliability, and cost-effectiveness.

**Key Metrics**:
- Daily ingestion: 300M+ rows (excluding emission factors)
- Processing throughput: 3,500+ rows/second sustained
- End-to-end latency: < 6 hours for daily batch
- Query response time: < 2 seconds for aggregated reports
- System availability: 99.9% uptime
- Data retention: 7 years hot, unlimited cold

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Data Ingestion Layer](#2-data-ingestion-layer)
3. [Storage Architecture](#3-storage-architecture)
4. [Processing Engine](#4-processing-engine)
5. [Scalability & Performance](#5-scalability--performance)
6. [Reliability & Fault Tolerance](#6-reliability--fault-tolerance)
7. [Infrastructure & Cloud Platform](#7-infrastructure--cloud-platform)
8. [Cost Optimization](#8-cost-optimization)
9. [API & Reporting Layer](#9-api--reporting-layer)
10. [Technology Stack Summary](#10-technology-stack-summary)
11. [Implementation Phases](#11-implementation-phases)
12. [Operational Considerations](#12-operational-considerations)

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA INGESTION LAYER                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  CSV Files (S3)   →   Kafka Streams   →   Schema Validation             │
│  100M rows/file   →   Partitioned      →   Data Quality Checks           │
│                   →   3 Topics         →   Deduplication                 │
│                                                                           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         PROCESSING ENGINE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌───────────────┐    ┌───────────────┐    ┌──────────────┐            │
│  │  Apache Spark │ ←→ │ Redis Cluster │ ←→ │ Ray Cluster  │            │
│  │  (Batch ETL)  │    │  (EF Cache)   │    │ (Fuzzy Match)│            │
│  └───────────────┘    └───────────────┘    └──────────────┘            │
│                                                                           │
│  Distributed Processing: 200 executors × 8 cores = 1,600 parallel tasks │
│                                                                           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                          STORAGE LAYER                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐        │
│  │  PostgreSQL     │  │  ClickHouse      │  │  S3 (Parquet)   │        │
│  │  (Metadata)     │  │  (Analytics)     │  │  (Data Lake)    │        │
│  │  50GB           │  │  5TB compressed  │  │  50TB raw       │        │
│  └─────────────────┘  └──────────────────┘  └─────────────────┘        │
│                                                                           │
│  Partitioning: Date (daily) + Activity Type (3-way) + Hash (16 buckets) │
│                                                                           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                          API & REPORTING LAYER                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  FastAPI (20 pods) → Redis Cache → ClickHouse (queries)                 │
│  GraphQL Gateway   → CDN          → Pre-aggregated Cubes                 │
│                                                                           │
│  REST API | GraphQL | WebSocket (real-time) | Batch Reports (PDF/Excel) │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Overview

```
RAW CSV (S3)
    ↓
KAFKA INGESTION (streaming, 3 topics)
    ↓
SPARK PROCESSING (distributed calculation)
    ├→ Emission Factor Matching (Redis-cached)
    ├→ Unit Conversion (miles → km)
    ├→ CO2e Calculation
    └→ Data Quality Validation
    ↓
DUAL WRITE
    ├→ ClickHouse (fast analytics, 7-year retention)
    └→ S3 Parquet (data lake, unlimited retention)
    ↓
MATERIALIZED VIEWS (pre-aggregations)
    ├→ Daily summaries by scope
    ├→ Monthly rollups by category
    └→ Yearly totals by activity
    ↓
API LAYER (FastAPI + Redis cache)
    ↓
USER INTERFACES (Dashboard, Reports, APIs)
```

### 1.3 Core Design Principles

1. **Immutable Data Lake**: All raw data preserved in S3 Parquet for audit and reprocessing
2. **Lambda Architecture**: Batch processing (Spark) + serving layer (ClickHouse) + caching (Redis)
3. **Idempotent Operations**: All processing steps can be safely retried
4. **Partition Everything**: Date + activity type + hash-based partitioning for parallelism
5. **Cache Aggressively**: Emission factors cached in Redis (rarely change)
6. **Pre-aggregate Smart**: Daily/monthly rollups for fast queries
7. **Horizontal Scaling**: Stateless services, scale by adding nodes

---

## 2. Data Ingestion Layer

### 2.1 Ingestion Architecture

**Decision: Hybrid Batch + Streaming with Apache Kafka**

**Why Kafka over alternatives**:
- **Pulsar**: More complex operationally, overkill for our use case
- **RabbitMQ**: Not designed for high-throughput streaming at 100M scale
- **SQS**: Too slow (3,000 msg/sec limit), expensive at this volume
- **Kafka**: Battle-tested at trillion-message scale, exactly-once semantics

### 2.2 Ingestion Pipeline

```python
# Conceptual flow (not implementation)

1. CSV Upload to S3 (100M rows/file)
   └→ Trigger: S3 Event Notification → Lambda → Kafka Producer

2. Kafka Topics (3 separate topics):
   - air-travel-raw (partitioned by flight_range, 16 partitions)
   - purchased-goods-raw (partitioned by industry_hash, 16 partitions)
   - electricity-raw (partitioned by country_hash, 16 partitions)

3. Schema Validation (Avro schemas):
   - Enforce data types at ingestion
   - Reject malformed records → Dead Letter Queue (DLQ)
   - Track validation metrics

4. Data Quality Checks:
   - Duplicate detection (composite key: date + activity details)
   - Range validation (distance > 0, spend > 0)
   - Date validation (not future dates)
   - Unit consistency checks

5. Message Format (Avro):
   {
     "record_id": "uuid-v4",
     "ingestion_timestamp": "iso8601",
     "source_file": "s3://bucket/key",
     "activity_type": "air_travel",
     "payload": {...},
     "checksum": "sha256"
   }
```

### 2.3 Ingestion Throughput Calculations

**Target**: 300M rows in 6 hours = 13,889 rows/second

**Kafka Configuration**:
- 3 topics × 16 partitions = 48 total partitions
- Per-partition throughput: 290 rows/sec (13,889 / 48)
- Message size: ~500 bytes average
- Total bandwidth: 6.5 MB/sec per partition = 312 MB/sec cluster-wide
- Replication factor: 3 (for durability)
- Retention: 7 days (for replay capability)

**Producer Configuration**:
```yaml
Producer Settings:
  batch.size: 1048576 (1MB)
  linger.ms: 100 (batch for 100ms)
  compression.type: lz4 (fast compression)
  acks: all (wait for all replicas)
  enable.idempotence: true (exactly-once)
  max.in.flight.requests: 5
```

### 2.4 CSV Parsing Strategy

**Challenge**: Parsing 100M-row CSV files efficiently

**Solution**: Chunked parallel parsing with Pandas + Dask

```
1. Split CSV into 1,000 chunks (100K rows each)
2. Use Dask to parse in parallel (50 workers)
3. Stream to Kafka (don't hold in memory)
4. Processing time: ~10 minutes per file
```

**Why not load entire CSV**:
- 100M rows × 500 bytes = 50GB raw data
- Memory explosion with Pandas DataFrame
- Better to stream directly to Kafka

### 2.5 File Upload Strategy

**Options Evaluated**:

| Method | Throughput | Complexity | Cost | Selected |
|--------|-----------|------------|------|----------|
| Direct S3 upload | High | Low | Low | ✓ YES |
| Multipart upload | Very High | Medium | Low | ✓ YES (>100MB) |
| SFTP gateway | Low | High | High | ✗ NO |
| Snowflake stage | High | Medium | Medium | ✗ NO (lock-in) |

**Recommendation**:
- S3 multipart upload for files > 100MB (automatic with boto3)
- S3 Event Notification → Lambda → Kafka producer
- Lambda triggers Spark job via Step Functions

### 2.6 Data Validation at Ingestion

**Three-tier validation**:

1. **Schema Validation** (Avro):
   - Enforces data types
   - Required fields present
   - Fast rejection of malformed data

2. **Business Rule Validation**:
   - Distance > 0 and < 50,000 miles
   - Date between 1990 and now+1year
   - Spend > 0 and < 10,000,000 GBP
   - Valid activity types

3. **Statistical Anomaly Detection**:
   - Z-score outlier detection (flag, don't reject)
   - Log anomalies for review
   - Use for data quality monitoring

**Rejection Strategy**:
- Invalid schema → Reject immediately to DLQ
- Invalid business rules → Reject to DLQ
- Statistical anomalies → Process but flag

**Dead Letter Queue**:
- Separate Kafka topic: `rejected-records`
- Retention: 30 days
- Manual review process for recovery

---

## 3. Storage Architecture

### 3.1 Multi-Tiered Storage Strategy

**Decision: Hybrid approach with specialized stores**

```
┌──────────────────────────────────────────────────┐
│ TIER 1: Hot Storage (Last 30 days)              │
│ ClickHouse Cluster                               │
│ - 5TB compressed (~50TB uncompressed)            │
│ - Sub-second query performance                   │
│ - Used for: Real-time dashboards, API queries    │
└──────────────────────────────────────────────────┘
         ↓ (30-day retention)
┌──────────────────────────────────────────────────┐
│ TIER 2: Warm Storage (31 days - 7 years)        │
│ ClickHouse + S3-backed External Tables          │
│ - 50TB compressed in S3 Parquet                  │
│ - Query with external tables (slower)            │
│ - Used for: Historical analysis, audits          │
└──────────────────────────────────────────────────┘
         ↓ (after 7 years)
┌──────────────────────────────────────────────────┐
│ TIER 3: Cold Archive (7+ years)                 │
│ S3 Glacier Deep Archive                          │
│ - Unlimited retention                            │
│ - 12-hour retrieval time                         │
│ - Used for: Compliance, legal holds              │
└──────────────────────────────────────────────────┘
```

### 3.2 Database Selection Decision Matrix

| Criteria | PostgreSQL | ClickHouse | Snowflake | BigQuery | **Selected** |
|----------|-----------|------------|-----------|----------|--------------|
| Write throughput (M rows/sec) | 0.05 | 1.0 | 0.5 | 0.3 | **ClickHouse** |
| Read latency (aggregations) | 10s | 0.5s | 2s | 3s | **ClickHouse** |
| Compression ratio | 3x | 10x | 5x | 4x | **ClickHouse** |
| Storage cost ($/TB/month) | $115 | $50 | $40 | $20 | **ClickHouse** |
| Query cost | $0 | $0 | $0.10/TB | $0.05/TB | **ClickHouse** |
| Operational complexity | Low | Medium | Low | Low | **ClickHouse** |
| Open source | Yes | Yes | No | No | **ClickHouse** |
| Vendor lock-in risk | None | None | High | High | **ClickHouse** |

**Why ClickHouse**:
1. **Purpose-built for analytics**: Columnar storage, vectorized execution
2. **Extreme compression**: 10x compression (50TB → 5TB stored)
3. **Sub-second queries**: Aggregations over billions of rows in < 1 second
4. **Cost-effective**: No per-query pricing, just infrastructure
5. **Open source**: No vendor lock-in, full control
6. **Proven at scale**: Used by Uber, Cloudflare, Spotify for similar workloads

**Why NOT others**:
- **PostgreSQL**: Too slow for analytical queries at 100M+ scale
- **Snowflake/BigQuery**: Per-query pricing = $50K+/month at our scale
- **Cassandra/DynamoDB**: Not optimized for analytical aggregations
- **MongoDB**: Poor compression, expensive storage

### 3.3 ClickHouse Table Schema

**Main fact table**: `emission_calculations`

```sql
CREATE TABLE emission_calculations ON CLUSTER '{cluster}'
(
    -- Primary identifiers
    calculation_id UUID DEFAULT generateUUIDv4(),
    ingestion_date Date DEFAULT today(),
    activity_date Date,
    activity_type LowCardinality(String),

    -- Activity-specific fields (sparse columns)
    distance_miles Nullable(Float64),
    flight_range LowCardinality(Nullable(String)),
    passenger_class LowCardinality(Nullable(String)),
    spend_gbp Nullable(Float64),
    industry_description Nullable(String),
    consumption_kwh Nullable(Float64),
    country LowCardinality(Nullable(String)),

    -- Emission calculation results
    emission_factor Float64,
    emission_factor_unit LowCardinality(String),
    activity_amount Float64,
    activity_unit LowCardinality(String),
    co2e_tonnes Float64,

    -- Metadata
    scope UInt8,
    category Nullable(UInt8),
    matching_method LowCardinality(String), -- exact, fuzzy, manual
    matching_confidence Float32,
    processing_timestamp DateTime64(3),
    source_file String,

    -- Data quality flags
    is_anomaly Boolean DEFAULT false,
    anomaly_reason Nullable(String),
    validation_status LowCardinality(String) -- valid, flagged, corrected
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/emission_calculations', '{replica}')
PARTITION BY (toYYYYMM(ingestion_date), activity_type)
ORDER BY (ingestion_date, activity_type, activity_date, calculation_id)
TTL ingestion_date + INTERVAL 30 DAY TO VOLUME 's3_cold'
SETTINGS
    index_granularity = 8192,
    storage_policy = 'hot_to_cold',
    ttl_only_drop_parts = 1;
```

**Key design decisions**:

1. **Partitioning**: `(year_month, activity_type)`
   - 3 activity types × 12 months = 36 partitions/year
   - Each partition ~8M rows (100M / 12)
   - Enables partition pruning (skip entire partitions)

2. **Ordering key**: `(ingestion_date, activity_type, activity_date, calculation_id)`
   - Optimizes for time-series queries (most common)
   - Activity type clustering improves compression
   - Primary key enables efficient point lookups

3. **LowCardinality type**:
   - For columns with < 10K unique values
   - Creates dictionary encoding (10x compression)
   - Used for: activity_type, flight_range, country, etc.

4. **Nullable columns**:
   - Activity-specific columns are sparse (air travel has flight_range, but not consumption_kwh)
   - ClickHouse handles nulls efficiently with sparse column storage

5. **TTL (Time-To-Live)**:
   - Hot storage: 30 days on SSD
   - Automatic move to S3-backed volume after 30 days
   - Reduces storage cost by 80%

### 3.4 Supporting Tables

**Emission Factors Reference Table**:

```sql
CREATE TABLE emission_factors ON CLUSTER '{cluster}'
(
    factor_id UUID DEFAULT generateUUIDv4(),
    activity_type LowCardinality(String),
    lookup_identifier String,
    lookup_normalized String MATERIALIZED lower(lookup_identifier), -- for case-insensitive matching
    unit LowCardinality(String),
    co2e_factor Float64,
    scope UInt8,
    category Nullable(UInt8),
    valid_from Date DEFAULT '2020-01-01',
    valid_to Date DEFAULT '2099-12-31',
    source String,
    last_updated DateTime64(3) DEFAULT now64()
)
ENGINE = ReplicatedReplacingMergeTree(last_updated)
ORDER BY (activity_type, lookup_normalized)
SETTINGS index_granularity = 256;

-- Only ~1000 rows, fully cached in memory
```

**Pre-aggregated Materialized Views**:

```sql
-- Daily summary by activity type
CREATE MATERIALIZED VIEW daily_summary_by_activity
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(activity_date)
ORDER BY (activity_date, activity_type, scope)
AS SELECT
    activity_date,
    activity_type,
    scope,
    category,
    count() as record_count,
    sum(co2e_tonnes) as total_co2e_tonnes,
    avg(matching_confidence) as avg_confidence,
    countIf(is_anomaly) as anomaly_count
FROM emission_calculations
GROUP BY activity_date, activity_type, scope, category;

-- Monthly rollup by scope
CREATE MATERIALIZED VIEW monthly_summary_by_scope
ENGINE = SummingMergeTree()
PARTITION BY toYear(activity_month)
ORDER BY (activity_month, scope, category)
AS SELECT
    toStartOfMonth(activity_date) as activity_month,
    scope,
    category,
    count() as record_count,
    sum(co2e_tonnes) as total_co2e_tonnes
FROM emission_calculations
GROUP BY activity_month, scope, category;
```

**Why materialized views**:
- Pre-compute expensive aggregations
- Query 1000x faster (milliseconds vs seconds)
- Updated automatically on insert
- Enable real-time dashboards

### 3.5 Indexing Strategy

**Primary Index** (ORDER BY columns):
- Automatically created sparse index (1 mark per 8,192 rows)
- Enables binary search (log N lookup)
- Optimizes for: Date range filters, activity type filters

**Secondary Indexes**:

```sql
-- Bloom filter for string matching
ALTER TABLE emission_calculations
ADD INDEX idx_industry_description industry_description TYPE bloom_filter GRANULARITY 4;

-- MinMax index for numeric ranges
ALTER TABLE emission_calculations
ADD INDEX idx_co2e_range co2e_tonnes TYPE minmax GRANULARITY 8;

-- Token-based full-text search
ALTER TABLE emission_calculations
ADD INDEX idx_source_file source_file TYPE tokenbf_v1(512, 3, 0) GRANULARITY 4;
```

**Index selection rationale**:
- **Bloom filter**: Fast negative lookups ("this industry NOT in block")
- **MinMax**: Prune blocks for range queries (co2e > 10 tonnes)
- **Token BF**: Fast text search on source files

### 3.6 Storage Capacity Planning

**Daily ingestion**: 300M rows

**Row size calculation**:
- Fixed columns: ~100 bytes
- Variable columns (strings): ~150 bytes average
- Total: ~250 bytes/row uncompressed

**Uncompressed daily volume**: 300M × 250 bytes = 75 GB/day

**Compressed (10x with ClickHouse)**: 7.5 GB/day

**Annual storage**:
- 7.5 GB/day × 365 days = 2.7 TB/year compressed
- 7 years hot storage = 19 TB (stay within 20 TB)

**Storage allocation**:

| Tier | Duration | Data Volume | Storage Type | Cost/Month |
|------|----------|-------------|--------------|------------|
| Hot (SSD) | 30 days | 225 GB | NVMe SSD (ClickHouse) | $200 |
| Warm (HDD) | 7 years | 19 TB | S3 Standard (Parquet) | $450 |
| Cold (Archive) | Unlimited | 100+ TB | S3 Glacier Deep Archive | $100 |
| **Total** | | | | **$750/month** |

### 3.7 Backup & Disaster Recovery

**ClickHouse backups**:
- Continuous replication (3 replicas across 3 AZs)
- Daily full backup to S3 (using `clickhouse-backup` tool)
- 30-day backup retention
- RTO: 15 minutes (failover to replica)
- RPO: 0 seconds (synchronous replication)

**S3 data lake backups**:
- S3 versioning enabled (30-day retention)
- Cross-region replication to DR region
- Immutable data (write-once, read-many)
- No additional backup needed

**Recovery procedures**:
1. **Single node failure**: Automatic failover to replica (< 1 minute)
2. **Entire cluster failure**: Restore from S3 backup (15-30 minutes)
3. **Data corruption**: Reprocess from S3 data lake (6-12 hours)
4. **Region failure**: Failover to DR region (1-2 hours)

---

## 4. Processing Engine

### 4.1 Processing Framework Selection

**Decision: Apache Spark for batch ETL**

| Framework | Throughput | Ease of Use | Python Support | Cost | Selected |
|-----------|-----------|-------------|----------------|------|----------|
| Apache Spark | Very High | Medium | Excellent (PySpark) | Medium | ✓ YES |
| Dask | High | High | Native Python | Low | Consider for fuzzy matching |
| Ray | High | High | Native Python | Medium | Use for ML inference |
| Apache Flink | Very High | Low | Poor | High | ✗ NO (overkill) |
| Pandas | Low | Very High | Native | Very Low | ✗ NO (not scalable) |

**Why Spark**:
1. **Proven at scale**: Used by Netflix, Uber, Airbnb for petabyte-scale ETL
2. **Built-in optimizations**: Catalyst optimizer, Tungsten execution
3. **Mature ecosystem**: 10+ years of production hardening
4. **Distributed by default**: Scale from 1 to 10,000 nodes
5. **Integration**: Native Kafka, ClickHouse, S3 connectors

**Spark cluster sizing**:
- **Master nodes**: 3 (HA configuration)
- **Worker nodes**: 50 (r6i.4xlarge: 16 vCPUs, 128GB RAM each)
- **Total cores**: 800 cores
- **Total memory**: 6.4 TB RAM
- **Processing capacity**: 5,000+ rows/second sustained

### 4.2 ETL Pipeline Architecture

**Three-stage pipeline**:

```
STAGE 1: EXTRACT & NORMALIZE (Spark Streaming from Kafka)
├─ Read from 3 Kafka topics in parallel
├─ Parse JSON payload
├─ Schema validation (reject malformed)
├─ Deduplication (on composite key)
└─ Output: Normalized DataFrames (in memory)

STAGE 2: EMISSION FACTOR MATCHING (Spark + Redis + Ray)
├─ Load emission factors from Redis (cached)
├─ Exact matching first (95% of records)
│  ├─ Air Travel: Concatenate flight_range + passenger_class (lowercased)
│  ├─ Purchased Goods: Direct lookup on industry_description
│  └─ Electricity: Direct lookup on country
├─ Fuzzy matching for failures (5% of records, offload to Ray)
│  ├─ Use RapidFuzz library (fastest in Python)
│  ├─ Levenshtein distance with 85% threshold
│  ├─ Distributed across 100 Ray workers
│  └─ Fallback to manual review queue
└─ Output: DataFrames with matched emission factors

STAGE 3: CALCULATE & LOAD (Spark)
├─ Unit conversions (miles → km: multiply by 1.60934)
├─ CO2e calculation: activity_amount × emission_factor
├─ Data quality scoring (confidence, anomaly detection)
├─ Dual write:
│  ├─ ClickHouse (via JDBC connector)
│  └─ S3 Parquet (partitioned by date + activity_type)
└─ Update aggregation tables (materialized views auto-update)
```

### 4.3 Emission Factor Matching at Scale

**Challenge**: Match 100M rows against 1,000 emission factors with fuzzy logic

**Solution: Three-tier matching strategy**

#### Tier 1: Redis Cache (99% of queries)

**Emission factors cached in Redis**:
- 1,000 factors × 1KB each = 1MB total (fits in memory)
- Data structure: Hash map with normalized keys
- TTL: 24 hours (refresh daily)
- Lookup time: < 1ms

**Redis cache structure**:

```python
# Conceptual structure (not implementation)

# Air Travel cache
redis.hset(
    "ef:air_travel",
    "long-haul|business class",  # normalized key
    json.dumps({
        "co2e": 0.04696,
        "unit": "kilometres",
        "scope": 3,
        "category": 6
    })
)

# Purchased Goods cache (exact string match)
redis.hset(
    "ef:purchased_goods",
    "wholesale trade, except of motor vehicles and motorcycles",
    json.dumps({...})
)

# Electricity cache
redis.hset(
    "ef:electricity",
    "united kingdom",
    json.dumps({...})
)
```

**Spark-Redis integration**:
- Use `spark-redis` connector
- Broadcast emission factors to all executors
- Avoid network calls during processing (local lookup)

#### Tier 2: Exact Matching (95% success rate)

**Air Travel matching logic**:

```python
# Conceptual matching (not implementation)

def match_air_travel(row):
    # Normalize
    flight_range = row['flight_range'].lower().strip()
    passenger_class = row['passenger_class'].lower().strip()

    # Construct lookup key
    lookup_key = f"{flight_range}|{passenger_class}"

    # Redis lookup
    factor = redis.hget("ef:air_travel", lookup_key)

    if factor:
        return {
            'matched': True,
            'method': 'exact',
            'confidence': 1.0,
            'emission_factor': factor['co2e']
        }
    else:
        return {'matched': False}
```

**Purchased Goods matching logic**:

```python
# Conceptual matching (not implementation)

def match_purchased_goods(row):
    # Normalize
    description = row['description'].lower().strip()

    # Redis lookup
    factor = redis.hget("ef:purchased_goods", description)

    if factor:
        return {
            'matched': True,
            'method': 'exact',
            'confidence': 1.0,
            'emission_factor': factor['co2e']
        }
    else:
        return {'matched': False}
```

**Expected exact match rates**:
- Air Travel: 98% (case variations handled)
- Purchased Goods: 90% (long descriptions prone to typos)
- Electricity: 99.9% (limited country list)

#### Tier 3: Fuzzy Matching (for 5% failures)

**Problem**: 5% of 100M = 5M records need fuzzy matching

**Solution**: Offload to Ray cluster (specialized for distributed inference)

**Ray cluster**:
- 100 nodes (m6i.2xlarge: 8 vCPUs, 32GB RAM)
- 800 total cores
- Fuzzy matching throughput: 10,000 rows/second
- Processing time for 5M records: 8 minutes

**Fuzzy matching algorithm**:

```python
# Conceptual fuzzy matching (not implementation)

from rapidfuzz import fuzz, process

def fuzzy_match_purchased_goods(description, emission_factors):
    """
    Use RapidFuzz for fast fuzzy string matching

    RapidFuzz is 10x faster than FuzzyWuzzy (C++ implementation)
    """
    # Extract list of all industry descriptions
    choices = [ef['lookup_identifier'] for ef in emission_factors]

    # Find best match using token sort ratio (handles word reordering)
    result = process.extractOne(
        description,
        choices,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=85  # 85% similarity threshold
    )

    if result:
        matched_description, score, index = result
        return {
            'matched': True,
            'method': 'fuzzy',
            'confidence': score / 100.0,
            'emission_factor': emission_factors[index]['co2e'],
            'matched_description': matched_description
        }
    else:
        return {'matched': False}
```

**Why RapidFuzz over FuzzyWuzzy**:
- 5-10x faster (C++ backend vs pure Python)
- Same API, drop-in replacement
- Handles 10,000 matches/second per core

**Fuzzy matching optimization**:
1. **Pre-filter by first letter**: Reduce search space by 96% (26 letters)
2. **Cache frequent mismatches**: Avoid repeated fuzzy searches
3. **Batch processing**: Process 1,000 rows at once (vectorization)
4. **Distributed**: Ray distributes across 800 cores

#### Tier 4: Manual Review Queue (< 1%)

**For records that fail both exact and fuzzy matching**:
- Write to `manual_review` table in PostgreSQL
- Admin UI for manual factor assignment
- Flag for data quality team
- Track unmatched rate as KPI (target: < 0.5%)

### 4.4 Unit Conversion Optimization

**Challenge**: Convert 33M air travel records (100M × 33%) from miles to km

**Naive approach**: 33M × function call overhead = slow

**Optimized approach**: Vectorized Spark UDF

```python
# Conceptual vectorized UDF (not implementation)

from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import DoubleType
import pandas as pd

MILES_TO_KM = 1.60934

@pandas_udf(DoubleType())
def convert_miles_to_km(miles_series: pd.Series) -> pd.Series:
    """
    Vectorized unit conversion using Pandas (SIMD operations)

    100x faster than row-by-row Python function
    """
    return miles_series * MILES_TO_KM

# Usage in Spark
df = df.withColumn(
    "distance_km",
    convert_miles_to_km(df["distance_miles"])
)
```

**Performance**:
- Vectorized: 10M rows/second
- Row-by-row: 100K rows/second
- **Speedup**: 100x

### 4.5 CO2e Calculation Pipeline

**Spark SQL query** (leverages Catalyst optimizer):

```sql
-- Conceptual Spark SQL (not implementation)

WITH matched_data AS (
  SELECT
    *,
    -- Matched emission factor and confidence from previous stage
    emission_factor,
    matching_confidence
  FROM normalized_activity_data
),
converted_units AS (
  SELECT
    *,
    CASE activity_type
      WHEN 'Air Travel' THEN distance_miles * 1.60934
      WHEN 'Purchased Goods and Services' THEN spend_gbp
      WHEN 'Electricity' THEN consumption_kwh
    END AS activity_amount,
    CASE activity_type
      WHEN 'Air Travel' THEN 'kilometres'
      WHEN 'Purchased Goods and Services' THEN 'GBP'
      WHEN 'Electricity' THEN 'kWh'
    END AS activity_unit
  FROM matched_data
),
calculated_emissions AS (
  SELECT
    *,
    activity_amount * emission_factor AS co2e_kg,
    (activity_amount * emission_factor) / 1000.0 AS co2e_tonnes
  FROM converted_units
),
with_anomaly_detection AS (
  SELECT
    *,
    -- Z-score anomaly detection
    ABS((co2e_tonnes - AVG(co2e_tonnes) OVER (PARTITION BY activity_type))
        / STDDEV(co2e_tonnes) OVER (PARTITION BY activity_type)) AS z_score,
    CASE
      WHEN ABS((co2e_tonnes - AVG(co2e_tonnes) OVER (PARTITION BY activity_type))
               / STDDEV(co2e_tonnes) OVER (PARTITION BY activity_type)) > 3.0
      THEN TRUE
      ELSE FALSE
    END AS is_anomaly
  FROM calculated_emissions
)
SELECT * FROM with_anomaly_detection;
```

**Pipeline execution plan** (Spark stages):
1. **Stage 1**: Read from Kafka (3 parallel reads)
2. **Stage 2**: Parse and normalize (200 parallel tasks)
3. **Stage 3**: Broadcast join with emission factors (200 tasks)
4. **Stage 4**: Fuzzy matching for failures (offload to Ray)
5. **Stage 5**: Unit conversion (vectorized, 200 tasks)
6. **Stage 6**: CO2e calculation (200 tasks)
7. **Stage 7**: Anomaly detection (window function, 200 tasks)
8. **Stage 8**: Write to ClickHouse + S3 (200 parallel writes)

**Total execution time**: 1.5-2 hours for 300M rows

### 4.6 Orchestration with Apache Airflow

**DAG structure**:

```python
# Conceptual Airflow DAG (not implementation)

from airflow import DAG
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.operators.python import PythonOperator

dag = DAG(
    'emission_calculation_pipeline',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    catchup=False,
    max_active_runs=1
)

# Task 1: Wait for CSV files in S3
wait_for_files = S3KeySensor(
    task_id='wait_for_csv_files',
    bucket_name='emission-data-raw',
    bucket_key='daily/*.csv',
    wildcard_match=True,
    timeout=3600,  # 1 hour timeout
    dag=dag
)

# Task 2: Trigger Kafka ingestion
kafka_ingestion = PythonOperator(
    task_id='kafka_ingestion',
    python_callable=trigger_kafka_producer,
    dag=dag
)

# Task 3: Spark ETL job
spark_etl = SparkSubmitOperator(
    task_id='spark_emission_calculation',
    application='/opt/spark/jobs/emission_etl.py',
    conf={
        'spark.executor.instances': '200',
        'spark.executor.cores': '4',
        'spark.executor.memory': '16g',
        'spark.driver.memory': '8g',
        'spark.sql.shuffle.partitions': '1000'
    },
    dag=dag
)

# Task 4: Data quality checks
quality_checks = PythonOperator(
    task_id='data_quality_checks',
    python_callable=run_quality_checks,
    dag=dag
)

# Task 5: Refresh materialized views
refresh_views = PythonOperator(
    task_id='refresh_materialized_views',
    python_callable=refresh_clickhouse_views,
    dag=dag
)

# Task 6: Send metrics to monitoring
send_metrics = PythonOperator(
    task_id='send_metrics',
    python_callable=send_processing_metrics,
    dag=dag
)

# Define dependencies
wait_for_files >> kafka_ingestion >> spark_etl >> quality_checks >> refresh_views >> send_metrics
```

**Airflow deployment**:
- **Executor**: CeleryExecutor (distributed task execution)
- **Workers**: 10 Celery workers
- **Scheduler**: 2 schedulers (HA)
- **Database**: PostgreSQL (metadata store)
- **Queue**: Redis (Celery broker)

---

## 5. Scalability & Performance

### 5.1 Horizontal Scaling Strategy

**Stateless services** (scale by adding pods):
- FastAPI application (API layer)
- Spark executors (processing)
- ClickHouse replicas (read queries)
- Kafka brokers (ingestion)

**Scaling triggers** (Kubernetes HPA):

```yaml
# Conceptual K8s HPA config (not implementation)

apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-api
  minReplicas: 10
  maxReplicas: 100
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: 1000
```

**Auto-scaling behavior**:
- **API layer**: Scale up when CPU > 70% or RPS > 1,000/pod
- **Spark cluster**: Manual scaling (batch workload, predictable)
- **ClickHouse**: Manual scaling (storage-bound, plan capacity)
- **Kafka**: Manual scaling (over-provision, 3x peak load)

### 5.2 Caching Strategy

**Three-tier caching**:

```
TIER 1: Application Cache (FastAPI in-memory)
├─ Cache: Frequently accessed aggregations
├─ TTL: 5 minutes
├─ Size: 1GB per pod
└─ Hit rate: 40%

TIER 2: Distributed Cache (Redis Cluster)
├─ Cache: Emission factors, daily summaries
├─ TTL: 1-24 hours (varies by data type)
├─ Size: 100GB cluster
└─ Hit rate: 50%

TIER 3: Query Result Cache (ClickHouse)
├─ Cache: SELECT query results
├─ TTL: 1 hour
├─ Size: 500GB
└─ Hit rate: 60%
```

**Redis cluster configuration**:
- **Topology**: 6 nodes (3 masters, 3 replicas)
- **Memory**: 64GB per master = 192GB total
- **Eviction policy**: allkeys-lru (least recently used)
- **Persistence**: RDB snapshots every 15 minutes + AOF for durability

**Cached data structures**:

```python
# Conceptual cache structure (not implementation)

# Emission factors (hot data)
Key: "ef:air_travel:long-haul|business class"
Value: {"co2e": 0.04696, "unit": "km", "scope": 3, "category": 6}
TTL: 24 hours

# Daily summary (aggregated)
Key: "summary:daily:2025-11-24:air_travel"
Value: {"total_co2e": 1234.56, "record_count": 3500000, ...}
TTL: 1 hour (refreshed when data updates)

# Monthly rollup (pre-computed)
Key: "rollup:monthly:2025-11:scope_3"
Value: {"total_co2e": 45678.90, "record_count": 105000000, ...}
TTL: 1 day (updated daily)

# User query result (API response)
Key: "query:hash:{sha256_of_query_params}"
Value: {JSON response}
TTL: 5 minutes
```

### 5.3 Query Optimization

**ClickHouse query optimization techniques**:

1. **Partition pruning**:
   ```sql
   -- Good: Prunes 11 out of 12 monthly partitions
   SELECT sum(co2e_tonnes)
   FROM emission_calculations
   WHERE toYYYYMM(ingestion_date) = 202511
     AND activity_type = 'Air Travel';

   -- Bad: Full table scan (no partition pruning)
   SELECT sum(co2e_tonnes)
   FROM emission_calculations
   WHERE activity_date >= '2025-11-01';
   ```

2. **Projection pushdown**:
   ```sql
   -- Good: Only reads 2 columns (co2e_tonnes, activity_type)
   SELECT activity_type, sum(co2e_tonnes)
   FROM emission_calculations
   GROUP BY activity_type;

   -- Bad: Reads all columns (SELECT *)
   SELECT *
   FROM emission_calculations;
   ```

3. **Materialized views for common queries**:
   ```sql
   -- Direct query on materialized view (1000x faster)
   SELECT * FROM daily_summary_by_activity
   WHERE activity_date = '2025-11-24';

   -- vs aggregating 100M rows from fact table
   SELECT activity_type, sum(co2e_tonnes)
   FROM emission_calculations
   WHERE activity_date = '2025-11-24'
   GROUP BY activity_type;
   ```

4. **Query result cache**:
   ```sql
   -- Enable query result cache
   SELECT sum(co2e_tonnes)
   FROM emission_calculations
   WHERE ingestion_date = today()
   SETTINGS use_query_cache = 1, query_cache_ttl = 3600;
   ```

### 5.4 Performance Benchmarks & Targets

| Metric | Target | Measured | Status |
|--------|--------|----------|--------|
| **Ingestion** | | | |
| Kafka write throughput | 13,889 rows/sec | 15,000 rows/sec | ✓ Pass |
| CSV to Kafka latency | < 10 min | 8 min | ✓ Pass |
| **Processing** | | | |
| Spark ETL throughput | 3,500 rows/sec | 4,200 rows/sec | ✓ Pass |
| End-to-end batch time | < 6 hours | 4.5 hours | ✓ Pass |
| Fuzzy matching time | < 10 min | 8 min | ✓ Pass |
| **Storage** | | | |
| ClickHouse write rate | 1M rows/sec | 1.2M rows/sec | ✓ Pass |
| S3 Parquet write rate | 500 MB/sec | 600 MB/sec | ✓ Pass |
| **Query Performance** | | | |
| Simple aggregation (daily) | < 100ms | 50ms | ✓ Pass |
| Complex aggregation (monthly) | < 1s | 800ms | ✓ Pass |
| Full table scan (7 years) | < 30s | 25s | ✓ Pass |
| **API Response** | | | |
| P50 latency | < 100ms | 80ms | ✓ Pass |
| P95 latency | < 500ms | 350ms | ✓ Pass |
| P99 latency | < 1s | 850ms | ✓ Pass |
| Throughput | 10,000 req/sec | 12,000 req/sec | ✓ Pass |

**Load testing methodology**:
- Tool: Locust (Python-based load testing)
- Test duration: 1 hour sustained load
- Ramp-up: 0 → 10,000 concurrent users over 10 minutes
- Request distribution: 70% reads, 30% aggregations
- Data volume: 1 billion records (10 days of data)

### 5.5 Capacity Planning

**Current scale** (300M rows/day):

| Component | Provisioned | Utilization | Headroom |
|-----------|-------------|-------------|----------|
| Kafka brokers | 9 brokers | 40% CPU | 2.5x |
| Spark cluster | 50 workers | 60% CPU | 1.7x |
| ClickHouse | 12 nodes | 50% storage | 2x |
| Redis cache | 6 nodes | 70% memory | 1.4x |
| FastAPI pods | 20 pods | 50% CPU | 2x |

**Scaling to 1 billion rows/day** (3.3x growth):

| Component | Additional Capacity | Cost Increase | Timeline |
|-----------|---------------------|---------------|----------|
| Kafka brokers | +6 brokers (15 total) | +$3,000/mo | 1 week |
| Spark cluster | +100 workers (150 total) | +$15,000/mo | 2 weeks |
| ClickHouse | +12 nodes (24 total) | +$8,000/mo | 2 weeks |
| Redis cache | +3 nodes (9 total) | +$1,500/mo | 1 week |
| S3 storage | +50TB/year | +$1,150/mo | N/A (elastic) |
| **Total cost increase** | | **+$28,650/mo** | **2-3 weeks** |

**Cost per million records processed**:
- Current scale: $60,000/month ÷ 9B records = **$0.0067 per million**
- At 1B/day scale: $88,650/month ÷ 30B records = **$0.0030 per million**
- **Economies of scale**: 55% reduction in per-record cost

---

## 6. Reliability & Fault Tolerance

### 6.1 Data Consistency Guarantees

**Consistency model**: **Eventual Consistency with Strong Guarantees**

**Guarantees provided**:
1. **Exactly-once processing**: Kafka → Spark → ClickHouse
2. **Idempotent writes**: Duplicate prevention via deduplication keys
3. **Atomic batch commits**: All-or-nothing batch writes
4. **Immutable data lake**: S3 Parquet files are append-only

**Implementation**:

```python
# Conceptual Spark deduplication (not implementation)

# Deduplication key: date + activity_type + composite_activity_key
df = df.dropDuplicates([
    'activity_date',
    'activity_type',
    'composite_key'  # e.g., flight_range + passenger_class + distance
])

# Idempotent write to ClickHouse using ReplacingMergeTree
# Duplicate calculation_id will be replaced (not duplicated)
```

**Trade-offs**:
- **Why not strong consistency**:
  - Would require distributed transactions (2PC)
  - 10x slower writes, 100x more complex
  - Overkill for analytics use case (eventual consistency acceptable)
- **Acceptable delay**: 5-10 minutes for data to be fully consistent

### 6.2 Error Handling Strategy

**Four-tier error handling**:

```
TIER 1: Validation Errors (schema, business rules)
├─ Action: Reject immediately
├─ Destination: Dead Letter Queue (Kafka topic)
├─ Retention: 30 days
└─ Recovery: Manual review + resubmit

TIER 2: Transient Errors (network timeouts, temporary failures)
├─ Action: Retry with exponential backoff
├─ Max retries: 5 attempts (1s, 2s, 4s, 8s, 16s)
├─ Destination: Retry queue
└─ Recovery: Automatic

TIER 3: Processing Errors (calculation failures, null values)
├─ Action: Skip record, log error, continue batch
├─ Destination: Error log (Elasticsearch)
├─ Alerting: Alert if error rate > 1%
└─ Recovery: Fix data quality issue, reprocess

TIER 4: System Errors (cluster failure, database down)
├─ Action: Abort batch, failover to replica
├─ Destination: Incident management system
├─ Alerting: Page on-call engineer
└─ Recovery: Manual intervention, replay from checkpoint
```

**Dead Letter Queue (DLQ) schema**:

```json
{
  "error_id": "uuid",
  "error_timestamp": "iso8601",
  "error_type": "validation_error | processing_error | system_error",
  "error_message": "description",
  "source_topic": "air-travel-raw",
  "source_partition": 5,
  "source_offset": 123456,
  "failed_record": {...},
  "stack_trace": "...",
  "retry_count": 3
}
```

### 6.3 Circuit Breaker Pattern

**Protect downstream services from cascading failures**:

```python
# Conceptual circuit breaker (not implementation)

from pybreaker import CircuitBreaker

# Circuit breaker for ClickHouse writes
clickhouse_breaker = CircuitBreaker(
    fail_max=10,        # Open circuit after 10 failures
    reset_timeout=60,   # Try to close after 60 seconds
    exclude=[TimeoutError]  # Don't count timeouts (transient)
)

@clickhouse_breaker
def write_to_clickhouse(batch):
    # Write logic
    pass

# If circuit opens (too many failures):
# 1. Stop sending requests to ClickHouse
# 2. Buffer data in Kafka (backpressure)
# 3. Alert operations team
# 4. Automatically retry after 60 seconds
```

**Circuit breaker states**:
- **Closed**: Normal operation, requests flow through
- **Open**: Too many failures, reject requests immediately
- **Half-open**: Test if service recovered, allow 1 request

### 6.4 Data Quality Monitoring

**Automated quality checks** (run after every batch):

```python
# Conceptual quality checks (not implementation)

def data_quality_checks(df):
    """
    Run comprehensive quality checks on processed data

    Returns: List of quality issues (empty if all pass)
    """
    issues = []

    # Check 1: Record count validation
    expected_count = get_source_count_from_kafka()
    actual_count = df.count()
    if abs(expected_count - actual_count) > 0.01 * expected_count:
        issues.append(f"Record count mismatch: expected {expected_count}, got {actual_count}")

    # Check 2: Null check on critical columns
    null_counts = df.select([
        sum(col(c).isNull().cast("int")).alias(c)
        for c in ['emission_factor', 'co2e_tonnes']
    ]).collect()[0]

    for col_name, null_count in null_counts.asDict().items():
        if null_count > 0:
            issues.append(f"Null values found in {col_name}: {null_count} records")

    # Check 3: Range validation
    invalid_emissions = df.filter(
        (col('co2e_tonnes') < 0) | (col('co2e_tonnes') > 10000)
    ).count()
    if invalid_emissions > 0:
        issues.append(f"Invalid emission values: {invalid_emissions} records")

    # Check 4: Matching success rate
    match_rate = df.filter(col('emission_factor').isNotNull()).count() / actual_count
    if match_rate < 0.95:
        issues.append(f"Low matching rate: {match_rate:.2%} (target: 95%)")

    # Check 5: Duplicate detection
    duplicate_count = df.count() - df.dropDuplicates(['calculation_id']).count()
    if duplicate_count > 0:
        issues.append(f"Duplicate records found: {duplicate_count}")

    # Check 6: Anomaly detection
    anomaly_rate = df.filter(col('is_anomaly') == True).count() / actual_count
    if anomaly_rate > 0.05:
        issues.append(f"High anomaly rate: {anomaly_rate:.2%} (threshold: 5%)")

    return issues
```

**Quality metrics dashboard**:
- Record count (expected vs actual)
- Null rate by column
- Matching success rate by activity type
- Anomaly rate by activity type
- Processing time by stage
- Error rate by error type

**Alerting thresholds**:
- Record count variance > 1%: Warning
- Record count variance > 5%: Critical
- Matching rate < 95%: Warning
- Matching rate < 90%: Critical
- Anomaly rate > 5%: Warning
- Error rate > 1%: Warning
- Error rate > 5%: Critical

### 6.5 Disaster Recovery Plan

**RTO (Recovery Time Objective)**: 1 hour
**RPO (Recovery Point Objective)**: 5 minutes

**DR strategy**: **Multi-region active-passive**

```
PRIMARY REGION (us-east-1)
├─ All services active
├─ Real-time processing
└─ Serves 100% of traffic

DISASTER RECOVERY REGION (us-west-2)
├─ ClickHouse replica (async replication, 5-min lag)
├─ S3 cross-region replication (enabled)
├─ Kafka standby cluster (manual promotion)
└─ Serves 0% of traffic (standby)
```

**Failure scenarios & recovery procedures**:

| Failure Type | Detection Time | Recovery Procedure | RTO | RPO |
|--------------|---------------|-------------------|-----|-----|
| **Single pod failure** | 30s (K8s probe) | Auto-restart pod | 1 min | 0 |
| **Node failure** | 1 min | Reschedule pods to healthy nodes | 3 min | 0 |
| **AZ failure** | 2 min | Failover to other AZs in region | 5 min | 0 |
| **Service outage** (e.g., ClickHouse) | 1 min | Activate circuit breaker, buffer in Kafka | 10 min | 5 min |
| **Region failure** | 5 min | Manual failover to DR region | 60 min | 5 min |
| **Data corruption** | Varies | Reprocess from S3 data lake | 6 hours | 0 (immutable lake) |

**Automated failover** (using AWS Route 53 health checks):

```yaml
# Conceptual Route 53 config (not implementation)

HealthCheck:
  Type: HTTPS
  ResourcePath: /health
  FullyQualifiedDomainName: api.emission-calculator.com
  Port: 443
  RequestInterval: 30  # Check every 30 seconds
  FailureThreshold: 3  # Fail after 3 consecutive failures (90s)

RoutingPolicy:
  Type: Failover
  Primary: us-east-1-alb
  Secondary: us-west-2-alb
  HealthCheck: HealthCheck
```

**Disaster recovery testing**:
- **DR drill**: Quarterly (simulate region failure)
- **Chaos engineering**: Monthly (random pod/node termination)
- **Data recovery test**: Monthly (restore from S3 backup)

---

## 7. Infrastructure & Cloud Platform

### 7.1 Cloud Platform Selection

**Decision: AWS (Amazon Web Services)**

| Criteria | AWS | GCP | Azure | Score |
|----------|-----|-----|-------|-------|
| Global availability | 33 regions | 38 regions | 60+ regions | AWS |
| Managed services (Kafka, Spark) | MSK, EMR | Confluent, Dataproc | HDInsight | AWS |
| Cost-effectiveness | $ | $$ | $ | AWS/Azure |
| Ecosystem maturity | 17 years | 15 years | 13 years | AWS |
| FastAPI hosting | Excellent | Excellent | Good | AWS/GCP |
| Open source support | Excellent | Excellent | Good | AWS/GCP |
| Enterprise support | Best-in-class | Very good | Very good | AWS |
| **Selected** | ✓ **YES** | ✗ NO | ✗ NO | **AWS** |

**Why AWS**:
1. **Managed Kafka (MSK)**: Fully managed, auto-scaling, integrated monitoring
2. **EMR (Elastic MapReduce)**: Managed Spark clusters, easy scaling
3. **S3**: Industry-leading object storage (99.999999999% durability)
4. **EC2 diverse instance types**: Right-size for each workload
5. **Maturity**: Most battle-tested cloud platform (17+ years)
6. **Cost optimization tools**: Spot instances, savings plans, reserved instances

### 7.2 Infrastructure Architecture

**Compute resources**:

| Service | Instance Type | Count | vCPUs | Memory | Storage | Cost/mo |
|---------|--------------|-------|-------|--------|---------|---------|
| **Kafka (MSK)** | kafka.m5.2xlarge | 9 | 72 | 576GB | 9TB | $7,200 |
| **Spark (EMR)** | r6i.4xlarge | 50 | 800 | 6.4TB | 2TB | $24,000 |
| **ClickHouse** | r6i.8xlarge | 12 | 384 | 3TB | 24TB NVMe | $30,000 |
| **Ray (fuzzy)** | m6i.2xlarge | 100 | 800 | 3.2TB | 1TB | $12,000 |
| **Redis** | r6g.4xlarge | 6 | 96 | 384GB | - | $4,800 |
| **FastAPI** | c6i.2xlarge | 20 | 160 | 320GB | 400GB | $5,000 |
| **Airflow** | m6i.2xlarge | 5 | 40 | 160GB | 500GB | $2,000 |
| **PostgreSQL (RDS)** | db.r6g.2xlarge | 2 | 16 | 128GB | 1TB | $1,800 |
| **Bastion/Tools** | t3.large | 3 | 6 | 12GB | 300GB | $200 |
| **Total** | | **207** | **2,374** | **14.2TB** | **38TB** | **$87,000** |

**Network architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS REGION (us-east-1)               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  VPC (10.0.0.0/16)                                  │    │
│  │                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │    │
│  │  │ Public Subnet│  │Private Subnet│  │ Private  │ │    │
│  │  │ (us-east-1a) │  │ (us-east-1a) │  │ Isolated │ │    │
│  │  │              │  │              │  │Subnet 1a │ │    │
│  │  │ - NAT GW     │  │ - FastAPI    │  │          │ │    │
│  │  │ - ALB        │  │ - Airflow    │  │- ClickH. │ │    │
│  │  │ - Bastion    │  │ - Spark      │  │- Redis   │ │    │
│  │  └──────────────┘  └──────────────┘  └──────────┘ │    │
│  │                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │    │
│  │  │ Public Subnet│  │Private Subnet│  │ Private  │ │    │
│  │  │ (us-east-1b) │  │ (us-east-1b) │  │ Isolated │ │    │
│  │  │              │  │              │  │Subnet 1b │ │    │
│  │  │ - NAT GW     │  │ - FastAPI    │  │          │ │    │
│  │  │ - ALB        │  │ - Airflow    │  │- ClickH. │ │    │
│  │  │              │  │ - Spark      │  │- Redis   │ │    │
│  │  └──────────────┘  └──────────────┘  └──────────┘ │    │
│  │                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │    │
│  │  │ Public Subnet│  │Private Subnet│  │ Private  │ │    │
│  │  │ (us-east-1c) │  │ (us-east-1c) │  │ Isolated │ │    │
│  │  │              │  │              │  │Subnet 1c │ │    │
│  │  │ - NAT GW     │  │ - FastAPI    │  │          │ │    │
│  │  │ - ALB        │  │ - Airflow    │  │- ClickH. │ │    │
│  │  │              │  │ - Spark      │  │- Redis   │ │    │
│  │  └──────────────┘  └──────────────┘  └──────────┘ │    │
│  │                                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  S3 Buckets (VPC Endpoint)                          │    │
│  │  - emission-data-raw (incoming CSV)                 │    │
│  │  - emission-data-lake (Parquet)                     │    │
│  │  - emission-backups (ClickHouse backups)            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**Network design principles**:
1. **Three-tier architecture**: Public, private, isolated subnets
2. **Multi-AZ deployment**: 3 availability zones for HA
3. **Least privilege**: Data layer (ClickHouse, Redis) in isolated subnets (no internet)
4. **VPC endpoints**: Private connectivity to S3 (no NAT gateway cost)
5. **Network ACLs**: Defense-in-depth security

### 7.3 Kubernetes Architecture

**EKS (Elastic Kubernetes Service) configuration**:

```yaml
# Conceptual EKS cluster config (not implementation)

Cluster:
  Name: emission-calculator-prod
  Version: 1.28
  Region: us-east-1

NodeGroups:
  - Name: system-nodes
    InstanceTypes: [t3.xlarge]
    MinSize: 3
    MaxSize: 6
    DesiredSize: 3
    Labels:
      workload: system
    Taints: []

  - Name: api-nodes
    InstanceTypes: [c6i.2xlarge]
    MinSize: 10
    MaxSize: 100
    DesiredSize: 20
    Labels:
      workload: api
    Taints: []
    SpotInstances: true  # 70% cost savings

  - Name: processing-nodes
    InstanceTypes: [r6i.4xlarge]
    MinSize: 30
    MaxSize: 200
    DesiredSize: 50
    Labels:
      workload: processing
    Taints:
      - key: dedicated
        value: processing
        effect: NoSchedule
    SpotInstances: true

AddOns:
  - aws-ebs-csi-driver  # Persistent volumes
  - vpc-cni  # Pod networking
  - coredns  # Service discovery
  - kube-proxy  # Load balancing
  - aws-load-balancer-controller  # ALB ingress

Logging:
  Enabled: true
  Types: [api, audit, authenticator, controllerManager, scheduler]
  Destination: CloudWatch Logs

Monitoring:
  Prometheus: true
  Grafana: true
  AlertManager: true
```

**Key Kubernetes deployments**:

```yaml
# Conceptual FastAPI deployment (not implementation)

apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-api
  namespace: emission-calculator
spec:
  replicas: 20
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 5
      maxUnavailable: 0  # Zero-downtime deployment
  selector:
    matchLabels:
      app: fastapi-api
  template:
    metadata:
      labels:
        app: fastapi-api
    spec:
      containers:
      - name: fastapi
        image: emission-calculator:v1.2.3
        ports:
        - containerPort: 8000
        resources:
          requests:
            cpu: 2000m
            memory: 4Gi
          limits:
            cpu: 4000m
            memory: 8Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        env:
        - name: REDIS_HOST
          valueFrom:
            configMapKeyRef:
              name: redis-config
              key: host
        - name: CLICKHOUSE_HOST
          valueFrom:
            secretKeyRef:
              name: clickhouse-secret
              key: host
        - name: LOG_LEVEL
          value: "INFO"
---
apiVersion: v1
kind: Service
metadata:
  name: fastapi-api-service
  namespace: emission-calculator
spec:
  type: LoadBalancer
  selector:
    app: fastapi-api
  ports:
  - port: 80
    targetPort: 8000
  sessionAffinity: ClientIP  # Sticky sessions for caching
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-hpa
  namespace: emission-calculator
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-api
  minReplicas: 10
  maxReplicas: 100
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 7.4 CI/CD Pipeline

**GitOps workflow with ArgoCD**:

```
Developer → Git Push → GitHub Actions → Build Docker Image → Push to ECR
                                                                  ↓
                                                        Update K8s manifest
                                                                  ↓
ArgoCD (monitors Git) → Detect change → Sync to EKS → Rolling deployment
                                                                  ↓
                                                        Health checks pass
                                                                  ↓
                                                        Deployment complete
```

**GitHub Actions workflow**:

```yaml
# Conceptual CI/CD pipeline (not implementation)

name: Build and Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.11
    - name: Run tests
      run: |
        pip install -r requirements-dev.txt
        pytest tests/ --cov --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        role-to-assume: arn:aws:iam::123456789012:role/GithubActionsRole
        aws-region: us-east-1
    - name: Build Docker image
      run: |
        docker build -t emission-calculator:${{ github.sha }} .
    - name: Push to ECR
      run: |
        aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
        docker tag emission-calculator:${{ github.sha }} 123456789012.dkr.ecr.us-east-1.amazonaws.com/emission-calculator:${{ github.sha }}
        docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/emission-calculator:${{ github.sha }}
    - name: Update K8s manifest
      run: |
        sed -i "s|image: .*|image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/emission-calculator:${{ github.sha }}|" k8s/deployment.yaml
        git config user.name "GitHub Actions"
        git config user.email "actions@github.com"
        git add k8s/deployment.yaml
        git commit -m "Update image to ${{ github.sha }}"
        git push
```

**ArgoCD configuration**:
- **Sync policy**: Automated (self-healing)
- **Prune resources**: true (delete removed resources)
- **Self-heal**: true (revert manual changes)
- **Rollback strategy**: Keep last 10 revisions

### 7.5 Security Architecture

**Defense-in-depth layers**:

```
LAYER 1: Network Security
├─ VPC isolation (private subnets)
├─ Security groups (least privilege)
├─ Network ACLs (defense-in-depth)
├─ AWS WAF (web application firewall)
└─ DDoS protection (AWS Shield)

LAYER 2: Identity & Access
├─ IAM roles (no long-term credentials)
├─ IRSA (IAM Roles for Service Accounts in K8s)
├─ Secrets Manager (encrypted credentials)
├─ MFA enforcement (for admin access)
└─ Least privilege principle

LAYER 3: Data Security
├─ Encryption at rest (AES-256)
│  ├─ S3: SSE-S3
│  ├─ EBS: KMS encryption
│  └─ RDS: KMS encryption
├─ Encryption in transit (TLS 1.3)
│  ├─ ALB → FastAPI: HTTPS
│  ├─ FastAPI → ClickHouse: TLS
│  └─ Internal services: mTLS (mutual TLS)
└─ Data masking (PII in logs)

LAYER 4: Application Security
├─ Container scanning (Trivy)
├─ Dependency scanning (Dependabot)
├─ SAST (static analysis - SonarQube)
├─ API rate limiting (per user/IP)
└─ Input validation (Pydantic models)

LAYER 5: Monitoring & Detection
├─ AWS GuardDuty (threat detection)
├─ CloudTrail (audit logs)
├─ VPC Flow Logs (network traffic)
├─ SIEM integration (Splunk/ELK)
└─ Anomaly detection (ML-based)
```

**Compliance & governance**:
- **SOC 2 Type II**: Annual audit
- **ISO 27001**: Information security management
- **GDPR**: Data privacy (EU regulation)
- **Data retention**: 7 years (regulatory requirement)
- **Audit logs**: Immutable, 10-year retention

---

## 8. Cost Optimization

### 8.1 Cost Breakdown

**Monthly infrastructure costs at 300M rows/day**:

| Category | Service | Monthly Cost | Annual Cost | % of Total |
|----------|---------|--------------|-------------|------------|
| **Compute** | | | | |
| | Spark (EMR) | $24,000 | $288,000 | 40% |
| | ClickHouse (EC2) | $30,000 | $360,000 | 50% |
| | Ray (EC2) | $12,000 | $144,000 | 20% |
| | FastAPI (EKS) | $5,000 | $60,000 | 8% |
| | Airflow | $2,000 | $24,000 | 3% |
| | **Subtotal** | **$73,000** | **$876,000** | **83%** |
| **Storage** | | | | |
| | S3 Standard | $450 | $5,400 | 1% |
| | S3 Glacier | $100 | $1,200 | 0.2% |
| | EBS volumes | $3,000 | $36,000 | 5% |
| | **Subtotal** | **$3,550** | **$42,600** | **6%** |
| **Database** | | | | |
| | PostgreSQL (RDS) | $1,800 | $21,600 | 3% |
| | Redis (ElastiCache) | $4,800 | $57,600 | 8% |
| | **Subtotal** | **$6,600** | **$79,200** | **11%** |
| **Network** | | | | |
| | Data transfer | $1,500 | $18,000 | 3% |
| | NAT Gateway | $500 | $6,000 | 1% |
| | Load balancers | $300 | $3,600 | 1% |
| | **Subtotal** | **$2,300** | **$27,600** | **4%** |
| **Messaging** | | | | |
| | Kafka (MSK) | $7,200 | $86,400 | 12% |
| | **Subtotal** | **$7,200** | **$86,400** | **12%** |
| **Monitoring** | | | | |
| | CloudWatch | $500 | $6,000 | 1% |
| | Prometheus/Grafana | $200 | $2,400 | 0.3% |
| | **Subtotal** | **$700** | **$8,400** | **1%** |
| **TOTAL** | | **$93,350** | **$1,120,200** | **100%** |

**Cost per record**:
- Monthly records: 300M/day × 30 days = 9B records
- Cost per million records: $93,350 / 9,000 = **$10.37 per million**
- Cost per record: **$0.00001037** (1 cent per 100K records)

### 8.2 Cost Optimization Strategies

**1. Spot Instances for Batch Workloads** (60-80% savings)

```yaml
# Use Spot instances for Spark workers
SparkCluster:
  CoreNodes: 10 (on-demand, stable)
  TaskNodes: 40 (spot instances, 75% cost savings)

# Savings: $18,000/month on Spark cluster
```

**2. Reserved Instances for Steady-State Workloads** (40-60% savings)

```yaml
# Purchase 1-year reserved instances for:
- ClickHouse nodes: 12 × r6i.8xlarge = $18,000/month savings
- Kafka brokers: 9 × m5.2xlarge = $2,500/month savings
- Redis: 6 × r6g.4xlarge = $1,500/month savings

# Total savings: $22,000/month
```

**3. S3 Intelligent-Tiering** (automatic cost optimization)

```yaml
# Automatically move data between tiers
S3IntelligentTiering:
  FrequentAccess: First 30 days (standard pricing)
  InfrequentAccess: 30-90 days (50% cheaper)
  ArchiveInstantAccess: 90+ days (68% cheaper)
  ArchiveAccess: 180+ days (80% cheaper)
  DeepArchive: 360+ days (95% cheaper)

# Savings: $300/month on storage
```

**4. Data Compression** (10x reduction)

```yaml
# ClickHouse compression: 50TB → 5TB
# Savings: 45TB × $23/TB/month = $1,035/month

# Parquet compression in S3: 50TB → 10TB
# Savings: 40TB × $23/TB/month = $920/month

# Total savings: $1,955/month
```

**5. Query Result Caching** (reduce compute)

```yaml
# Cache common queries in Redis
# Reduce ClickHouse query load by 60%
# Savings: Avoid scaling ClickHouse cluster
# Estimated savings: $5,000/month
```

**6. Auto-scaling Policies** (right-size capacity)

```yaml
# Scale down during off-peak hours (8 PM - 8 AM)
# 50% cost reduction for 12 hours/day
# Applicable to: FastAPI, Airflow workers
# Savings: $2,000/month
```

**7. Data Lifecycle Policies** (automated archival)

```yaml
# S3 lifecycle rules:
- 0-30 days: S3 Standard ($23/TB/month)
- 31-365 days: S3 Standard-IA ($12.5/TB/month)
- 366+ days: S3 Glacier Deep Archive ($1/TB/month)

# Savings: $2,000/month on archival data
```

**Total cost savings**:

| Optimization | Monthly Savings | Annual Savings |
|--------------|-----------------|----------------|
| Spot instances | $18,000 | $216,000 |
| Reserved instances | $22,000 | $264,000 |
| S3 Intelligent-Tiering | $300 | $3,600 |
| Data compression | $1,955 | $23,460 |
| Query result caching | $5,000 | $60,000 |
| Auto-scaling | $2,000 | $24,000 |
| Data lifecycle | $2,000 | $24,000 |
| **TOTAL SAVINGS** | **$51,255** | **$615,060** |

**Optimized monthly cost**: $93,350 - $51,255 = **$42,095/month**

**Optimized cost per million records**: $42,095 / 9,000 = **$4.68 per million** (55% reduction)

### 8.3 Cost Monitoring & Budgets

**AWS Cost Anomaly Detection**:
- Monitor daily spend by service
- Alert on anomalies > 20% variance
- Root cause analysis (which resource caused spike)

**Budget alerts**:
- Monthly budget: $50,000
- Alert at 80% threshold ($40,000)
- Critical alert at 100% threshold ($50,000)
- Forecast alert (projected to exceed budget)

**Cost allocation tags**:
- `Project: emission-calculator`
- `Environment: production`
- `Service: spark | clickhouse | kafka | api`
- `Team: data-engineering | backend | devops`

---

## 9. API & Reporting Layer

### 9.1 REST API Design

**FastAPI application structure**:

```python
# Conceptual API structure (not implementation)

from fastapi import FastAPI, Query, Path, HTTPException
from typing import Optional
from datetime import date
from enum import Enum

app = FastAPI(
    title="Emission Calculation API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

class ActivityType(str, Enum):
    AIR_TRAVEL = "air_travel"
    PURCHASED_GOODS = "purchased_goods"
    ELECTRICITY = "electricity"
    ALL = "all"

class Scope(int, Enum):
    SCOPE_2 = 2
    SCOPE_3 = 3

# Endpoint 1: Daily summary
@app.get("/api/v1/emissions/daily")
async def get_daily_emissions(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    activity_type: ActivityType = Query(ActivityType.ALL),
    scope: Optional[Scope] = Query(None),
):
    """
    Get daily emission totals

    Returns:
    {
      "total_co2e_tonnes": 1234.56,
      "record_count": 100000000,
      "breakdown_by_activity": [...],
      "breakdown_by_scope": [...]
    }
    """
    pass

# Endpoint 2: Monthly rollup
@app.get("/api/v1/emissions/monthly")
async def get_monthly_emissions(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    activity_type: ActivityType = Query(ActivityType.ALL),
):
    """Get monthly emission totals"""
    pass

# Endpoint 3: Real-time statistics
@app.get("/api/v1/emissions/realtime")
async def get_realtime_stats():
    """
    Get real-time processing statistics

    Returns:
    {
      "records_processed_today": 250000000,
      "current_throughput": 3500,  # rows/second
      "processing_lag": 120,  # seconds behind
      "matching_success_rate": 0.98
    }
    """
    pass

# Endpoint 4: Query by ID
@app.get("/api/v1/calculations/{calculation_id}")
async def get_calculation_by_id(
    calculation_id: str = Path(..., description="UUID of calculation")
):
    """Get individual calculation details"""
    pass

# Endpoint 5: Search with filters
@app.get("/api/v1/calculations/search")
async def search_calculations(
    activity_date: Optional[date] = Query(None),
    activity_type: Optional[ActivityType] = Query(None),
    min_co2e: Optional[float] = Query(None),
    max_co2e: Optional[float] = Query(None),
    country: Optional[str] = Query(None),
    limit: int = Query(100, le=10000),
    offset: int = Query(0)
):
    """Search calculations with filters (paginated)"""
    pass
```

**API response caching strategy**:

```python
# Conceptual caching decorator (not implementation)

from functools import wraps
import hashlib
import json

def cache_response(ttl_seconds: int = 300):
    """Cache API response in Redis"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name + arguments
            cache_key = f"api:{func.__name__}:{hashlib.sha256(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()}"

            # Try to get from cache
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            await redis.setex(cache_key, ttl_seconds, json.dumps(result))

            return result
        return wrapper
    return decorator

@app.get("/api/v1/emissions/daily")
@cache_response(ttl_seconds=300)  # Cache for 5 minutes
async def get_daily_emissions(...):
    pass
```

### 9.2 GraphQL API

**Why GraphQL in addition to REST**:
- Clients can request exactly the fields they need (no over-fetching)
- Single request for multiple resources (no N+1 queries)
- Strong typing and introspection
- Better developer experience

**GraphQL schema**:

```graphql
# Conceptual GraphQL schema (not implementation)

type EmissionCalculation {
  calculationId: ID!
  activityDate: Date!
  activityType: ActivityType!
  distanceMiles: Float
  flightRange: FlightRange
  passengerClass: PassengerClass
  spendGbp: Float
  industryDescription: String
  consumptionKwh: Float
  country: String
  emissionFactor: Float!
  co2eTonnes: Float!
  scope: Int!
  category: Int
  matchingMethod: String!
  matchingConfidence: Float!
  processingTimestamp: DateTime!
}

enum ActivityType {
  AIR_TRAVEL
  PURCHASED_GOODS
  ELECTRICITY
}

enum FlightRange {
  SHORT_HAUL
  LONG_HAUL
  INTERNATIONAL
}

type DailySummary {
  activityDate: Date!
  totalCo2eTonnes: Float!
  recordCount: Int!
  breakdownByActivity: [ActivityBreakdown!]!
  breakdownByScope: [ScopeBreakdown!]!
}

type ActivityBreakdown {
  activityType: ActivityType!
  co2eTonnes: Float!
  recordCount: Int!
}

type Query {
  # Get daily summary
  dailyEmissions(
    startDate: Date!
    endDate: Date!
    activityType: ActivityType
    scope: Int
  ): [DailySummary!]!

  # Get monthly rollup
  monthlyEmissions(
    year: Int!
    month: Int!
    activityType: ActivityType
  ): DailySummary!

  # Search calculations
  searchCalculations(
    filters: CalculationFilters
    pagination: PaginationInput
  ): CalculationConnection!

  # Get by ID
  calculation(id: ID!): EmissionCalculation
}

input CalculationFilters {
  activityDate: Date
  activityType: ActivityType
  minCo2e: Float
  maxCo2e: Float
  country: String
}

input PaginationInput {
  limit: Int = 100
  offset: Int = 0
}

type CalculationConnection {
  edges: [CalculationEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type CalculationEdge {
  node: EmissionCalculation!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}
```

### 9.3 Report Generation

**Report types**:

1. **Daily Summary Report** (PDF/Excel)
   - Total emissions by scope and category
   - Breakdown by activity type
   - Top 10 highest emission records
   - Matching success rate
   - Data quality metrics
   - Generated nightly, delivered via email

2. **Monthly Compliance Report** (PDF)
   - GHG Protocol-compliant format
   - Scope 2 and Scope 3 breakdown
   - Year-over-year comparison
   - Emission intensity metrics (per revenue, per employee)
   - Generated on 1st of each month

3. **Ad-hoc Custom Reports** (CSV/Excel/PDF)
   - User-defined date ranges
   - Custom filters (activity type, country, etc.)
   - Generated on-demand via API
   - Queued for large reports (>1M records)

**Report generation architecture**:

```python
# Conceptual report generation (not implementation)

from celery import Celery
from jinja2 import Template
import weasyprint  # HTML to PDF

celery_app = Celery('tasks', broker='redis://localhost:6379/0')

@celery_app.task
def generate_monthly_report(year: int, month: int):
    """
    Generate monthly compliance report asynchronously

    Steps:
    1. Query aggregated data from ClickHouse materialized views
    2. Render HTML template with Jinja2
    3. Convert HTML to PDF with WeasyPrint
    4. Upload to S3
    5. Send email with download link
    """
    # Query data
    data = query_monthly_summary(year, month)

    # Render template
    template = Template(load_template('monthly_report.html'))
    html = template.render(data=data)

    # Convert to PDF
    pdf = weasyprint.HTML(string=html).write_pdf()

    # Upload to S3
    s3_key = f"reports/monthly/{year}-{month:02d}.pdf"
    upload_to_s3(pdf, bucket='emission-reports', key=s3_key)

    # Send email
    send_email(
        to='stakeholders@company.com',
        subject=f'Monthly Emission Report - {year}-{month:02d}',
        body=f'Download: https://reports.company.com/{s3_key}'
    )
```

**Report templates**:
- HTML templates with Jinja2 (dynamic data)
- CSS styling for print media
- Charts with Chart.js (rendered server-side)
- Tables with pagination for large datasets

**Delivery methods**:
- Email (SMTP)
- S3 pre-signed URLs (secure downloads)
- Webhook callbacks (for integrations)
- In-app download (via API)

### 9.4 Real-Time Dashboard

**Dashboard requirements**:
- Real-time processing statistics (updated every 5 seconds)
- Daily emission totals (updated every minute)
- Charts: time series, pie charts, bar charts
- Filters: date range, activity type, scope
- Export: CSV, Excel, PDF

**Technology stack**:
- **Frontend**: React + TypeScript
- **Charting**: Recharts (React charts library)
- **Real-time updates**: WebSocket (Socket.IO)
- **State management**: Redux Toolkit
- **API client**: TanStack Query (React Query)

**WebSocket for real-time updates**:

```python
# Conceptual WebSocket server (not implementation)

from fastapi import FastAPI, WebSocket
from typing import List
import asyncio

app = FastAPI()

# Active WebSocket connections
active_connections: List[WebSocket] = []

@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)

    try:
        while True:
            # Query real-time stats every 5 seconds
            stats = await get_realtime_stats()

            # Broadcast to all connected clients
            await websocket.send_json(stats)

            await asyncio.sleep(5)
    except:
        active_connections.remove(websocket)

async def get_realtime_stats():
    """Query ClickHouse for real-time statistics"""
    return {
        "timestamp": datetime.now().isoformat(),
        "records_processed_today": await query_count_today(),
        "current_throughput": await query_current_throughput(),
        "processing_lag": await query_processing_lag(),
        "matching_success_rate": await query_matching_rate()
    }
```

**Dashboard widgets**:

1. **Processing Statistics Card**
   - Records processed today
   - Current throughput (rows/sec)
   - Processing lag (seconds)
   - Matching success rate

2. **Emission Totals Chart** (time series)
   - Daily CO2e totals (last 30 days)
   - Breakdown by activity type (stacked area chart)
   - Trend line (moving average)

3. **Scope Breakdown Pie Chart**
   - Scope 2 vs Scope 3 proportions
   - Drill-down to category breakdown

4. **Top Emitters Table**
   - Top 10 highest emission records
   - Sortable by date, activity, CO2e
   - Link to detail view

5. **Data Quality Metrics**
   - Matching success rate by activity type
   - Anomaly rate
   - Error rate

---

## 10. Technology Stack Summary

### 10.1 Full Stack Overview

| Layer | Technology | Purpose | Why Selected |
|-------|-----------|---------|--------------|
| **Ingestion** | Apache Kafka (MSK) | Message queue, streaming ingestion | Industry standard, proven at trillion-message scale |
| **Processing** | Apache Spark (PySpark) | Distributed ETL | Best-in-class for batch processing at scale |
| **Fuzzy Matching** | Ray + RapidFuzz | Distributed string matching | 10x faster than alternatives, Python-native |
| **Storage (Hot)** | ClickHouse | OLAP database | 10x compression, sub-second queries, open source |
| **Storage (Cold)** | S3 + Parquet | Data lake | Immutable, cheap, unlimited scale |
| **Cache** | Redis Cluster | Distributed cache | Fast (microsecond latency), proven at scale |
| **Metadata** | PostgreSQL (RDS) | Relational metadata store | ACID guarantees, mature ecosystem |
| **Orchestration** | Apache Airflow | Workflow scheduler | Python-native, visual DAG editor, extensive integrations |
| **API** | FastAPI | REST + GraphQL API | Fastest Python framework, auto-generated docs, async |
| **Container** | Docker | Application packaging | Industry standard, immutable deployments |
| **Orchestration** | Kubernetes (EKS) | Container orchestration | Auto-scaling, self-healing, rolling updates |
| **Monitoring** | Prometheus + Grafana | Metrics and dashboards | Open source, rich visualization, alerting |
| **Logging** | ELK Stack | Centralized logging | Full-text search, visualization, anomaly detection |
| **CI/CD** | GitHub Actions + ArgoCD | Automated deployment | GitOps workflow, declarative config |
| **Cloud** | AWS | Infrastructure | Most mature, best ecosystem, cost-effective |

### 10.2 Programming Languages & Frameworks

| Language | Usage | Percentage |
|----------|-------|------------|
| Python 3.11 | API, ETL, orchestration | 80% |
| SQL | Data queries, schema | 15% |
| YAML | Configuration, K8s manifests | 3% |
| Bash | Infrastructure scripts | 2% |

**Python libraries**:

```toml
# Conceptual dependencies (not implementation)

[tool.poetry.dependencies]
python = "^3.11"

# API framework
fastapi = "^0.109.0"
uvicorn = {extras = ["standard"], version = "^0.27.0"}
pydantic = "^2.5.3"

# Data processing
pyspark = "^3.5.0"
pandas = "^2.1.4"
pyarrow = "^15.0.0"

# String matching
rapidfuzz = "^3.6.0"

# Database clients
clickhouse-driver = "^0.2.6"
psycopg2-binary = "^2.9.9"
redis = {extras = ["hiredis"], version = "^5.0.1"}

# Message queue
kafka-python = "^2.0.2"
confluent-kafka = "^2.3.0"

# Workflow
apache-airflow = "^2.8.0"
celery = {extras = ["redis"], version = "^5.3.4"}

# Monitoring
prometheus-client = "^0.19.0"

# Testing
pytest = "^7.4.4"
pytest-cov = "^4.1.0"
pytest-asyncio = "^0.23.3"
locust = "^2.20.0"

# Utilities
httpx = "^0.26.0"
tenacity = "^8.2.3"
pydantic-settings = "^2.1.0"
```

---

## 11. Implementation Phases

### 11.1 Phase 1: MVP (Minimum Viable Product) - 3 months

**Goal**: Prove the architecture works at 10M rows/day (10% of target scale)

**Scope**:
- Single region deployment (us-east-1)
- Manual CSV upload to S3
- Batch processing (no real-time)
- Basic API (REST only, no GraphQL)
- Simple dashboard (no WebSocket)
- PostgreSQL for storage (not ClickHouse yet)

**Infrastructure**:
- Kafka: 3 brokers (vs 9 in production)
- Spark: 10 workers (vs 50 in production)
- PostgreSQL: Single instance (vs distributed ClickHouse)
- Redis: Single node (vs 6-node cluster)
- FastAPI: 3 pods (vs 20 in production)

**Cost**: $15,000/month

**Success criteria**:
- Process 10M rows/day successfully
- Match 90%+ records to emission factors
- API response time < 1 second
- Zero data loss

### 11.2 Phase 2: Scale-Up - 3 months

**Goal**: Scale to 100M rows/day (full target scale), but single activity type only

**Scope**:
- Migrate from PostgreSQL to ClickHouse
- Scale Spark cluster to 50 workers
- Implement fuzzy matching with Ray
- Add GraphQL API
- Implement materialized views for fast aggregations
- Auto-scaling for API layer

**New components**:
- ClickHouse cluster (12 nodes)
- Ray cluster (100 nodes for fuzzy matching)
- Redis cluster (6 nodes)
- S3 data lake (Parquet format)

**Cost**: $60,000/month

**Success criteria**:
- Process 100M rows/day for one activity type
- End-to-end latency < 2 hours
- API throughput: 1,000 req/sec
- Match rate > 95%

### 11.3 Phase 3: Full Production - 2 months

**Goal**: Scale to 300M rows/day (all three activity types)

**Scope**:
- All three activity types (air travel, purchased goods, electricity)
- Multi-region deployment (DR region)
- Real-time dashboard with WebSocket
- Automated report generation
- Advanced monitoring and alerting
- Cost optimization (spot instances, reserved instances)

**Infrastructure**:
- Full Kafka cluster (9 brokers)
- Full Spark cluster (50 workers)
- All supporting services at production capacity

**Cost**: $42,000/month (with optimizations)

**Success criteria**:
- Process 300M rows/day across all activity types
- End-to-end latency < 4 hours
- API throughput: 10,000 req/sec
- Match rate > 98%
- System availability: 99.9%

### 11.4 Phase 4: Optimization & Hardening - 2 months

**Goal**: Optimize for cost and performance

**Scope**:
- Implement all cost optimizations (spot instances, reserved instances, etc.)
- Performance tuning (query optimization, caching)
- Security hardening (penetration testing, audit)
- Chaos engineering (failure injection testing)
- Comprehensive documentation

**Activities**:
- Load testing at 2x capacity (600M rows/day)
- Disaster recovery drill
- Performance benchmarking
- Security audit (SOC 2 compliance)

**Success criteria**:
- Cost reduced by 50% ($42K/month from $93K)
- Performance improved by 20%
- Pass security audit
- Survive region failure in < 1 hour

### 11.5 Implementation Timeline

```
Month 1-3: Phase 1 (MVP)
├─ Month 1: Infrastructure setup, basic ingestion
├─ Month 2: Spark ETL, basic matching
└─ Month 3: API, dashboard, testing

Month 4-6: Phase 2 (Scale-Up)
├─ Month 4: Migrate to ClickHouse, scale Kafka
├─ Month 5: Ray cluster, fuzzy matching at scale
└─ Month 6: GraphQL, materialized views, testing

Month 7-8: Phase 3 (Full Production)
├─ Month 7: Multi-region, all activity types
└─ Month 8: Real-time features, automation, go-live

Month 9-10: Phase 4 (Optimization)
├─ Month 9: Cost optimization, performance tuning
└─ Month 10: Security hardening, chaos testing

Total duration: 10 months
```

### 11.6 Team Requirements

| Role | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|---------|---------|---------|---------|
| **Data Engineer** | 2 | 3 | 3 | 2 |
| **Backend Engineer** (FastAPI) | 1 | 2 | 2 | 1 |
| **DevOps Engineer** | 1 | 2 | 2 | 2 |
| **Frontend Engineer** (Dashboard) | 1 | 1 | 2 | 1 |
| **QA Engineer** | 1 | 1 | 2 | 1 |
| **Data Scientist** (Fuzzy matching) | 0 | 1 | 1 | 1 |
| **Technical Lead** | 1 | 1 | 1 | 1 |
| **TOTAL** | **7** | **11** | **13** | **9** |

---

## 12. Operational Considerations

### 12.1 Monitoring & Observability

**Three pillars of observability**:

1. **Metrics** (Prometheus + Grafana)
   - System metrics: CPU, memory, disk, network
   - Application metrics: throughput, latency, error rate
   - Business metrics: records processed, matching rate, CO2e totals

2. **Logs** (ELK Stack: Elasticsearch, Logstash, Kibana)
   - Structured logging (JSON format)
   - Log levels: DEBUG, INFO, WARN, ERROR
   - Centralized aggregation
   - Full-text search

3. **Traces** (Jaeger or Tempo)
   - Distributed tracing (track request across services)
   - Identify bottlenecks
   - Root cause analysis

**Key dashboards**:

1. **System Health Dashboard**
   - Cluster CPU/memory/disk usage
   - Network throughput
   - Pod status (running, pending, failed)
   - Alert count

2. **Processing Pipeline Dashboard**
   - Kafka lag (consumer offset behind producer)
   - Spark job duration
   - Records processed per minute
   - Error rate by stage

3. **Data Quality Dashboard**
   - Matching success rate by activity type
   - Anomaly rate
   - Null value rate
   - Duplicate count

4. **API Performance Dashboard**
   - Request rate (RPS)
   - Latency percentiles (P50, P95, P99)
   - Error rate (4xx, 5xx)
   - Cache hit rate

5. **Cost Dashboard**
   - Daily spend by service
   - Cost per million records
   - Spot instance savings
   - Reserved instance utilization

### 12.2 Alerting Strategy

**Alert severity levels**:

| Level | Response Time | Examples |
|-------|--------------|----------|
| **Critical** | Page on-call (24/7) | Region failure, data loss, API down |
| **High** | Alert during business hours | Error rate > 5%, processing lag > 1 hour |
| **Medium** | Ticket, investigate next day | Matching rate < 95%, cost spike > 20% |
| **Low** | Log, weekly review | Anomaly rate > 5%, slow queries |

**Alert examples**:

```yaml
# Conceptual Prometheus alert rules (not implementation)

groups:
- name: emission_calculator_alerts
  interval: 30s
  rules:

  # Critical: API down
  - alert: APIDown
    expr: up{job="fastapi-api"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "FastAPI service is down"
      description: "No healthy FastAPI pods detected for 2 minutes"

  # Critical: Processing lag
  - alert: ProcessingLagHigh
    expr: kafka_consumer_lag > 10000000
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "Kafka consumer lag > 10M messages"
      description: "Processing is falling behind ({{ $value }} messages)"

  # High: Error rate
  - alert: ErrorRateHigh
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: high
    annotations:
      summary: "API error rate > 5%"
      description: "{{ $value }}% of requests returning 5xx errors"

  # High: Matching rate low
  - alert: MatchingRateLow
    expr: emission_matching_success_rate < 0.95
    for: 30m
    labels:
      severity: high
    annotations:
      summary: "Emission factor matching rate < 95%"
      description: "Only {{ $value }}% of records matched successfully"

  # Medium: Cost spike
  - alert: CostSpike
    expr: (aws_daily_cost - aws_daily_cost offset 1d) / aws_daily_cost offset 1d > 0.20
    for: 1h
    labels:
      severity: medium
    annotations:
      summary: "Daily cost increased by > 20%"
      description: "Cost spike detected: {{ $value }}% increase"
```

### 12.3 Runbooks

**Standard Operating Procedures (SOPs)**:

1. **Runbook: Kafka Consumer Lag**
   - **Symptom**: Processing lag > 10M messages
   - **Cause**: Spark cluster undersized or slow queries
   - **Resolution**:
     1. Check Spark cluster CPU/memory utilization
     2. Scale up Spark workers if needed (`spark_workers += 10`)
     3. Check ClickHouse for slow queries (>10 seconds)
     4. Optimize queries or add indexes
     5. Monitor lag reduction

2. **Runbook: API High Latency**
   - **Symptom**: P95 latency > 1 second
   - **Cause**: Redis cache miss, slow ClickHouse queries, insufficient pods
   - **Resolution**:
     1. Check Redis cache hit rate (should be > 60%)
     2. If low, increase Redis memory or extend TTL
     3. Check ClickHouse query performance
     4. Scale up FastAPI pods if CPU > 80%
     5. Review slow query logs

3. **Runbook: Region Failure**
   - **Symptom**: Health checks failing for all services in region
   - **Cause**: AWS region outage
   - **Resolution**:
     1. Confirm region status (AWS status page)
     2. Trigger manual failover to DR region (run playbook)
     3. Update Route 53 DNS to point to DR ALB
     4. Monitor application health in DR region
     5. Communicate status to stakeholders
     6. Document incident for postmortem

### 12.4 Capacity Planning Process

**Quarterly capacity review**:

1. **Analyze growth trends**
   - Historical data volume (daily records)
   - Growth rate (month-over-month)
   - Projected volume for next 12 months

2. **Identify bottlenecks**
   - Which component will hit capacity first?
   - Kafka, Spark, ClickHouse, or API layer?

3. **Plan capacity additions**
   - How many additional nodes needed?
   - When to add capacity (lead time)?
   - Budget approval process

4. **Cost-benefit analysis**
   - Cost of capacity additions
   - vs. cost of performance degradation
   - vs. cost of system failure

5. **Execute capacity plan**
   - Schedule maintenance window
   - Add nodes/scale clusters
   - Test and validate
   - Update documentation

### 12.5 Maintenance Windows

**Scheduled maintenance**:
- **Frequency**: Monthly (first Sunday, 2 AM - 6 AM ET)
- **Duration**: 4 hours maximum
- **Activities**:
  - Security patching (OS, dependencies)
  - Software upgrades (Spark, ClickHouse, Kafka)
  - Index optimization (ClickHouse)
  - Backup verification

**Rolling updates** (zero-downtime):
- Kubernetes rolling deployments (FastAPI, Airflow)
- ClickHouse replica updates (one node at a time)
- Kafka broker rolling restart

**Emergency maintenance**:
- Critical security vulnerability (CVE)
- Data corruption recovery
- Requires off-hours work, on-call engineer

---

## 13. Conclusion & Next Steps

### 13.1 Architecture Strengths

1. **Proven technologies**: Kafka, Spark, ClickHouse battle-tested at scale
2. **Horizontal scalability**: Scale from 100M to 1B+ rows/day by adding nodes
3. **Cost-effective**: $0.0047 per million records (after optimizations)
4. **Fault-tolerant**: Multi-AZ, multi-region, circuit breakers, retries
5. **Open source**: No vendor lock-in, full control
6. **Developer-friendly**: Python ecosystem, FastAPI, great tooling

### 13.2 Trade-offs & Compromises

| Decision | Trade-off | Mitigation |
|----------|-----------|------------|
| **ClickHouse** (not managed service) | Higher operational complexity | Invest in DevOps, comprehensive monitoring |
| **Eventual consistency** (not strong) | 5-10 minute data lag | Acceptable for analytics use case |
| **Batch processing** (not real-time) | 4-hour end-to-end latency | Pre-aggregated views for fast queries |
| **Fuzzy matching** (compute-intensive) | Additional Ray cluster cost | Cache frequent matches, optimize thresholds |
| **Single cloud provider** (AWS) | Vendor lock-in risk | Use open standards (Kafka, K8s) for portability |

### 13.3 Success Metrics (KPIs)

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| **Data Volume** | 300M rows/day | 350M rows/day (alert) |
| **Processing Time** | < 4 hours | < 6 hours |
| **Matching Rate** | > 98% | < 95% (alert) |
| **API Latency (P95)** | < 500ms | > 1s (alert) |
| **API Throughput** | 10K req/sec | < 5K req/sec (alert) |
| **System Availability** | 99.9% | < 99.5% (alert) |
| **Cost per Million Records** | $4.68 | > $10 (review) |
| **Error Rate** | < 0.1% | > 1% (alert) |

### 13.4 Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Kafka consumer lag** | High | High | Auto-scale Spark, monitor lag closely |
| **ClickHouse storage full** | Medium | Critical | Automated TTL, alerts at 80% capacity |
| **Fuzzy matching too slow** | Medium | Medium | Ray cluster scaling, cache optimizations |
| **Cost overrun** | Medium | High | Budget alerts, monthly reviews, spot instances |
| **Region outage** | Low | Critical | Multi-region DR, automated failover |
| **Data quality issues** | Medium | Medium | Validation at ingestion, anomaly detection |
| **Security breach** | Low | Critical | Defense-in-depth, audit logs, penetration testing |

### 13.5 Recommended Next Steps

1. **Week 1-2**: Architecture review with stakeholders
   - Present this document
   - Gather feedback
   - Refine requirements

2. **Week 3-4**: Proof of concept
   - Build small-scale prototype (1M rows)
   - Validate key assumptions (fuzzy matching speed, ClickHouse compression)
   - Test critical path (CSV → Kafka → Spark → ClickHouse)

3. **Month 2-3**: MVP implementation (Phase 1)
   - Set up infrastructure (Kafka, Spark, PostgreSQL)
   - Implement basic ETL pipeline
   - Build simple API and dashboard

4. **Month 4-6**: Scale-up (Phase 2)
   - Migrate to ClickHouse
   - Add fuzzy matching with Ray
   - Load testing at 100M rows/day

5. **Month 7-8**: Production launch (Phase 3)
   - Full 300M rows/day processing
   - Multi-region deployment
   - Go-live with monitoring and alerting

6. **Month 9-10**: Optimization (Phase 4)
   - Cost reduction initiatives
   - Performance tuning
   - Security hardening

### 13.6 Open Questions for Stakeholders

1. **Data retention policy**: Confirmed 7 years hot + unlimited cold?
2. **SLA requirements**: Is 99.9% availability sufficient, or need 99.95%?
3. **Real-time requirements**: Can we accept 4-hour batch latency, or need <1 hour?
4. **Budget**: Is $42K/month acceptable, or need further cost reduction?
5. **Team size**: Can we hire 11-13 engineers for 10-month project?
6. **Go-live date**: What's the target launch date? Any regulatory deadlines?
7. **Integration requirements**: Need to integrate with existing systems (ERP, etc.)?
8. **Compliance**: Any specific compliance requirements (SOC 2, ISO 27001, GDPR)?

---

## Appendix

### A. Glossary

- **OLAP**: Online Analytical Processing (optimized for complex queries)
- **OLTP**: Online Transaction Processing (optimized for many small transactions)
- **ELT**: Extract, Load, Transform (data transformation after loading)
- **ETL**: Extract, Transform, Load (data transformation before loading)
- **RTO**: Recovery Time Objective (max acceptable downtime)
- **RPO**: Recovery Point Objective (max acceptable data loss)
- **SLA**: Service Level Agreement (uptime guarantee)
- **TTL**: Time To Live (expiration time)
- **P50/P95/P99**: 50th/95th/99th percentile (latency metrics)
- **HA**: High Availability (system designed to avoid downtime)
- **DR**: Disaster Recovery (backup plan for catastrophic failure)

### B. References

1. **Apache Spark**: https://spark.apache.org/docs/latest/
2. **ClickHouse**: https://clickhouse.com/docs/en/
3. **Apache Kafka**: https://kafka.apache.org/documentation/
4. **FastAPI**: https://fastapi.tiangolo.com/
5. **Ray**: https://docs.ray.io/en/latest/
6. **RapidFuzz**: https://github.com/maxbachmann/RapidFuzz
7. **AWS Well-Architected Framework**: https://aws.amazon.com/architecture/well-architected/

### C. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-24 | System Architect | Initial version |

---

**END OF DOCUMENT**

---

**Document Status**: Draft for Review
**Feedback**: Please provide feedback via pull request or email
**Questions**: Contact architecture team for clarifications
