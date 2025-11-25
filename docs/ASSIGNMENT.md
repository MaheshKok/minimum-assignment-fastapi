# Minimum Take-Home Task: Calculation Engine

**Source**: https://minimumeco.notion.site/Minimum-take-home-task-Calculation-Engine-2792246c49b5801fbc2fc5b2ce0e76ba

**Date**: November 22, 2025
**Status**: In Progress

---

## 🎯 Objective

Build a **calculation engine** that:
1. Processes activity data from CSV files
2. Matches it with emission factors
3. Calculates CO2e emissions
4. Outputs a comprehensive report

---

## 📁 Data Files Provided

Four CSV files are provided with the assignment:

### 1. **Emission_Factors.csv** (7.1 KB)
- **Purpose**: Normalized set of emission factors (lookup table)
- **Records**: 80 emission factors
- **Structure**:
  - `Activity`: Type of activity (Air Travel, Purchased Goods and Services, Electricity)
  - `Lookup identifiers`: Identifiers for matching (e.g., "Long-haul, Business class")
  - `Unit`: Unit of measurement (kilometres, GBP, kWh)
  - `CO2e`: CO2 equivalent emission factor (numeric)
  - `Scope`: GHG Protocol Scope (2 or 3)
  - `Category`: Scope 3 category number (1 or 6)

**Location**: `/Users/maheshkokare/PycharmProjects/minimum-assignment-fastapi/app/test/test_data/Emission_Factors.csv`

### 2. **Air_Travel.csv** (643 bytes)
- **Purpose**: Activity data for Business Travel (Scope 3, Category 6)
- **Records**: 9 flight records
- **Structure**:
  - `Date`: Travel date (DD/MM/YYYY format)
  - `Activity`: Always "Air Travel"
  - `Distance travelled`: Distance in miles (with comma separators)
  - `Distance units`: Always "miles"
  - `Flight range`: Short-haul, Long-haul, International
  - `Passenger class`: Business Class, Business class, Premium Economy class

**Critical Notes**:
- **TWO-COLUMN LOOKUP**: Match on both `Flight range` AND `Passenger class`
- **Unit conversion required**: Miles → Kilometres (multiply by 1.60934)
- **Case inconsistencies**: "Business Class" vs "Business class"

**Location**: `/Users/maheshkokare/PycharmProjects/minimum-assignment-fastapi/app/test/test_data/Air_Travel.csv`

### 3. **Purchased_Goods_and_Services.csv** (2.6 KB)
- **Purpose**: Activity data for Purchased Goods & Services (Scope 3, Category 1)
- **Records**: 29 purchase records
- **Structure**:
  - `Date`: Purchase date
  - `Activity`: Always "Purchased Goods and Services"
  - `Spend`: Amount in GBP
  - `Spend Unit`: Always "GBP"
  - `Description`: Long description of industry/sector

**Critical Notes**:
- **ONE-COLUMN LOOKUP**: Match on `Description` field
- Descriptions are very long (e.g., "Wholesale trade, except of motor vehicles and motorcycles")
- Must match exactly with `Lookup identifiers` in Emission_Factors.csv

**Location**: `/Users/maheshkokare/PycharmProjects/minimum-assignment-fastapi/app/test/test_data/Purchased_Goods_and_Services.csv`

### 4. **Electricity.csv** (25.4 KB)
- **Purpose**: Activity data for Electricity consumption (Scope 2)
- **Records**: 542 electricity usage records
- **Structure**:
  - `Date`: Usage date
  - `Activity`: Always "Electricity"
  - `Consumption`: Amount in kWh
  - `Consumption Unit`: Always "kWh"
  - `Country`: Always "United Kingdom"

**Critical Notes**:
- **ONE-COLUMN LOOKUP**: Match on `Country` field
- All records are UK-based
- Largest dataset (542 records)

**Location**: `/Users/maheshkokare/PycharmProjects/minimum-assignment-fastapi/app/test/test_data/Electricity.csv`

---

## 📋 Requirements

### Core Requirements

1. **Process Activity Data**
   - Read and process all three activity CSV files:
     - Air Travel
     - Purchased Goods & Services
     - Electricity
   - Handle different CSV formats for each activity type

2. **Emission Factor Lookup**
   - Match activity data with appropriate emission factors from `Emission_Factors.csv`
   - **Air Travel**: Two-column lookup (Flight range + Passenger class)
   - **Purchased Goods & Services**: One-column lookup (Description)
   - **Electricity**: One-column lookup (Country)

3. **Calculate CO2e Emissions**
   - Formula: `Activity Amount × Emission Factor = CO2e Emissions`
   - Examples:
     - Air Travel: `Distance (km) × CO2e factor = Emissions`
     - Purchased Goods: `Spend (GBP) × CO2e factor = Emissions`
     - Electricity: `Consumption (kWh) × CO2e factor = Emissions`
   - Calculate for **Scope 2** and **Scope 3** categories

4. **Output Report**
   - Generate comprehensive emissions report with breakdowns
   - Should include:
     - Total emissions
     - Breakdown by Scope (Scope 2, Scope 3)
     - Breakdown by Category (Category 1, Category 6 for Scope 3)
     - Breakdown by activity type
     - Individual record details (optional)

5. **Data Seeding**
   - Use provided CSV files to seed database or data structures
   - No need to create separate database migration

---

## 🔍 Key Considerations

### Data Format Differences
Each Activity Data CSV has a **different format** based on lookup requirements:

| Activity | Lookup Columns | Unit Conversion Needed |
|----------|---------------|----------------------|
| Air Travel | 2 (Flight range + Passenger class) | ✅ Yes (miles → km) |
| Purchased Goods | 1 (Description) | ❌ No |
| Electricity | 1 (Country) | ❌ No |

### Matching Challenges

1. **Case Sensitivity**
   - Air_Travel.csv has: "Business Class", "Business class"
   - Emission_Factors.csv has: "Business class"
   - **Solution**: Implement case-insensitive or fuzzy matching

2. **Long Descriptions**
   - Purchased Goods descriptions are very long
   - Must match exactly with Emission_Factors lookup identifiers
   - **Solution**: Use exact string matching or fuzzy matching with high threshold

3. **Combined Lookups**
   - Air Travel requires matching on TWO columns simultaneously
   - Example: Need to find factor for "Long-haul" + "Business class"
   - Emission_Factors format: "Long-haul, Business class" in `Lookup identifiers`
   - **Solution**: Construct combined lookup string or parse CSV identifier

### Unit Conversions

- **Air Travel**:
  - Input: miles
  - Emission factors: kilometres
  - Conversion: `1 mile = 1.60934 km`
  - Example: 3,459 miles = 5,568.51 km

- **Other Activities**: No conversion needed (GBP and kWh match directly)

---

## 🎯 Expected Outputs

### Report Structure (Example)

```
Carbon Emissions Report
=======================

SUMMARY
-------
Total CO2e Emissions: X.XXXX tonnes

SCOPE 2 (Purchased Electricity)
--------------------------------
Total: X.XXXX tonnes
Records processed: 542
Country: United Kingdom

SCOPE 3 (Indirect Emissions)
-----------------------------
Total: X.XXXX tonnes

Category 1: Purchased Goods and Services
  Total: X.XXXX tonnes
  Records processed: 29

Category 6: Business Travel (Air Travel)
  Total: X.XXXX tonnes
  Records processed: 9

  Breakdown by Flight Range:
    - Short-haul: X.XXXX tonnes
    - Long-haul: X.XXXX tonnes
    - International: X.XXXX tonnes

DETAILED BREAKDOWNS
-------------------
[Optional: Individual record calculations]
```

### Output Format Options
- JSON (machine-readable)
- CSV (tabular data)
- HTML (human-readable report)
- All of the above

---

## 🤖 AI Usage Policy

**Disclosure Required**: You may use AI-assisted IDE or other AI tooling, but must disclose:
- Which tools you used
- How you employed them

**Focus**: The task emphasizes:
- Your **thought process**
- Your understanding of **good code**
- Not just getting a working solution

### AI Tools Used (For Disclosure)

```
AI Tools Used:
1. Antigravity (Google Deepmind) - AI coding assistant
2. Claude Flow v2.7.0 - Agent orchestration for planning and implementation

Usage:
- Code architecture planning and decision documentation
- Implementation of calculation logic
- Testing strategy and test case generation
- Code review and optimization suggestions
- Documentation generation
```

---

## 📊 Data Quality Issues to Handle

Based on analysis of the CSV files:

1. **Date Format Variations**
   - Multiple date formats: DD/MM/YYYY
   - Need robust date parsing

2. **Number Formatting**
   - Comma separators in numbers (e.g., "3,459")
   - Need to strip commas before conversion

3. **Case Inconsistencies**
   - "Business Class" vs "Business class"
   - Implement case-insensitive matching

4. **Missing Data**
   - Check for empty values
   - Handle gracefully (skip or report)

5. **Data Type Conversions**
   - Strings to floats (for calculations)
   - Strings to dates (for timestamps)

---

## 🏗️ Implementation Approach

### Recommended Architecture

**Language**: Python (best for data processing)

**Key Libraries**:
- `pandas`: CSV processing and data manipulation
- `fuzzywuzzy` or `rapidfuzz`: Fuzzy string matching
- `pydantic`: Data validation
- `pytest`: Testing

**Design Pattern**: Modular service pattern with:
- Separate calculators for each activity type
- Central emission factor matcher
- Unit conversion service
- Report generator

### File Structure

```
minimum-assignment/
├── TASK.md                           # This file (assignment details)
├── data/
│   ├── Air_Travel.csv                # Input: flight data
│   ├── Purchased_Goods_and_Services.csv
│   ├── Electricity.csv
│   └── Emission_Factors.csv          # Lookup table
├── src/
│   ├── main.py                       # Entry point
│   ├── models/                       # Pydantic models
│   ├── calculators/                  # Activity calculators
│   │   ├── air_travel_calculator.py
│   │   ├── purchased_goods_calculator.py
│   │   └── electricity_calculator.py
│   ├── services/
│   │   ├── factor_matcher.py         # Emission factor matching
│   │   ├── unit_converter.py         # Unit conversions
│   │   └── report_generator.py       # Output formatting
│   └── utils/
│       └── csv_loader.py             # CSV reading utilities
├── tests/
│   ├── test_calculators.py
│   ├── test_matching.py
│   └── test_integration.py
├── output/                           # Generated reports
├── requirements.txt
└── README.md
```

---

## ✅ Acceptance Criteria

### Functional Requirements
- ✅ Reads all 4 CSV files successfully
- ✅ Matches emission factors correctly (>95% success rate)
- ✅ Calculates CO2e emissions accurately
- ✅ Handles unit conversions (miles → km)
- ✅ Generates comprehensive report
- ✅ Processes Scope 2 and Scope 3 correctly
- ✅ Handles case inconsistencies in matching

### Non-Functional Requirements
- ✅ Processing time: <5 seconds for all data
- ✅ Accuracy: 4 decimal places precision
- ✅ Error handling: Graceful failures with logging
- ✅ Code quality: Well-structured, readable, documented
- ✅ Testing: >90% test coverage

### Expected Results (Approximate)

**Total Records to Process**: 542 + 29 + 9 = 580 records

**Expected Breakdown**:
- Scope 2 (Electricity): 542 records, ~100-110 tonnes CO2e
- Scope 3, Category 1 (Purchased Goods): 29 records, ~10-15 tonnes CO2e
- Scope 3, Category 6 (Air Travel): 9 records, ~80-100 tonnes CO2e

*Note: Exact values depend on correct factor matching and calculations*

---

## 🔬 Testing Strategy

### Test Cases to Implement

1. **Unit Tests**
   - CSV loading and parsing
   - Unit conversions (miles → km)
   - Emission factor matching (exact, fuzzy, case-insensitive)
   - CO2e calculation accuracy
   - Report generation

2. **Integration Tests**
   - End-to-end processing of all CSV files
   - Correct matching for all activity types
   - Total emissions calculation

3. **Edge Cases**
   - Empty CSV files
   - Missing emission factors
   - Invalid data formats
   - Zero values
   - Duplicate records

4. **Data Quality Tests**
   - Comma-separated numbers
   - Case variations in matching
   - Long description matching
   - Multi-column lookups
