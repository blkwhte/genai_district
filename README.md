# Clever School District Data Generator (GenAI)
A robust Python tool that uses the Google Gemini API to generate high-fidelity, referentially intact synthetic data for testing Clever rostering integrations.

This tool simulates complex multi-district environments, creating coherent CSV datasets (Schools, Teachers, Staff, Students, Sections, Enrollments) suitable for testing Clever rostering integrations.

# Key Features

* **Dual ID Modes**: Choose between simple Sequential Integers (e.g., 100, 101) or complex State-Mapped Alphanumeric IDs (e.g., CA-01-8f4e2a).

* **Referential Integrity**: Guarantees that every Student_id in an enrollment file matches a "real" student, and every Teacher_id in a section file matches a "real" teacher wihtin the dataset.

* **Localized Context**: Automatically maps districts to real US states (e.g., "WestCharter" $\rightarrow$ California), adjusting zip codes, city names, and ID formats accordingly.

* **Smart Rostering**:Generates Co-Teaching scenarios.Creates Dual Role users (a user who is both a Teacher and Staff member).Enforces realistic DOB/Grade alignment.

* **Anti-Pattern Enforcement**: Actively prevents "lazy" AI generation (e.g., forbids sequential 12345 IDs) to ensure high-entropy, production-like data.

# Setup & Installation

### 1. Prerequisites
Python 3.9+
A Google Gemini API Key [Get one here](https://aistudio.google.com/app/apikey)

### 2. Installation

```
# 1. Clone the repository
git clone https://github.com/blkwhte/genai_district.git
cd genai_district

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a .env file in the root directory:

```
API_KEY=your_actual_api_key_here
```

# Usage
Run the generator:

```
python genai_district.py
```

The script is interactive. You will be prompted to configure the scale of your data:

1. Select ID Mode: sequential or alphanumeric.
2. District Count: How many distinct districts to generate.
3. School/Student Counts: defining the density of the data.

Output Structure
Data is generated into a school_district_data/ directory, organized by district name:

```
school_district_data/
├── WestCharter_Data/       (Mapped to California)
│   ├── schools.csv
│   ├── teachers.csv
│   ├── staff.csv
│   ├── students.csv
│   ├── sections.csv
│   └── enrollments.csv
├── NorthCharter_Data/      (Mapped to New York)
│   ├── ...
└── ...
```

# Technical Architecture
This tool operates in a Two-Phase Generation Strategy to ensure consistency within the context window limits of the LLM.

### Phase 1: Structure & Hierarchy
The model first generates the high-level "skeleton" of the district:

Establishes the District Schema (Name, State, Domain).

Generates Schools, Teachers, and Staff.

Why? This allows us to pass the exact list of Teacher_IDs into Phase 2, ensuring that sections are assigned to real teachers.

### Phase 2: Rostering & Logic
The model iterates through each school individually to generate Students, Sections, and Enrollments.

Context Isolation: By processing one school at a time, we avoid token overflow limits while maintaining the illusion of a massive, interconnected dataset.


##  Identifier Logic & Modes
You can toggle between two distinct logic modes during runtime:

### Mode A: Alphanumeric (Recommended)
Simulates modern, high-security production environments. IDs are non-sequential and state-aware.

| Entity | ID Format | Example |
| :--- | :--- | :--- |
| **School** | 5-6 char Hex | `8f4a1` |
| **Student** | State + SchoolCode + Number | `CA-01-10482910` |
| **Teacher** | State + 'T' + Number | `CA-T-923456` |

* Collision Protection: Each district is assigned a unique numeric prefix (e.g., 10, 11) for its internal numbers, ensuring that even if two districts use similar logic, their IDs never overlap.

### Mode B: Sequential
Simulates legacy systems. IDs are simple integers reserved in strictly non-overlapping blocks.

District 1 Base: 100,000

District 2 Base: 200,000

## CSV Schema Specification
1. **schools.csv**
    * Primary Key: School_id
    * Columns: School_id, School_name, School_number, Low_grade, High_grade, Principal, Principal_email, School_address, School_city, School_state, School_zip, School_phone
2. **teachers.csv**
    * Primary Key: Teacher_id
    * Columns: School_id, Teacher_id, Teacher_number, State_teacher_id, Teacher_email, First_name, Last_name, Title
3. **staff.csv**
    * Primary Key: Staff_id
    * Note: Includes Dual Role Users (users sharing an email with a teacher record) to test account merging logic.
    * Columns: School_id, Staff_id, Staff_email, First_name, Last_name, Department, Title
4. **students.csv**
    * Primary Key: Student_id
    * Columns: School_id, Student_id, Student_number, State_id, Last_name, First_name, Grade, Gender, DOB, Student_email
5. **sections.csv**
    * Primary Key: Section_id
    * Foreign Keys: Teacher_id (Links to teachers.csv)
    * Columns: School_id, Section_id, Teacher_id, Teacher_2_id, Name, Grade, Subject
6. **enrollments.csv**
    * Junction Table: Maps Student_id $\leftrightarrow$ Section_id.
    * Columns: School_id, Section_id, Student_id

# Limitations & Theoretical Constraints

### 1. The Token Limit (The "Hard" Wall)
The Gemini API has an output token limit per request. This script generates data per school. If you request too many students for a single school, the JSON response will be truncated, causing the script to fail for that school.Safe Limit: ~150-180 Students per School.Danger Zone: >250 Students per School.Workaround: If you need 5,000 students, generate 30 schools with 150 students each, rather than 1 school with 5,000 students.

### 2. API Quotas (The "Invisible" Wall)Google's Free Tier has daily request limits (approx. 1,500 requests/day).
   * Math: 1 District (5 Schools) = ~6 API Calls.
   * Capacity: You can generate roughly 250 districts per day on the free tier.
   * If you set SCHOOLS_PER_DISTRICT higher than ~15 to 20, Phase 1 will likely cut off mid-stream, resulting in invalid JSON.

### 3. Synchronous Execution
   * The script runs synchronously to preserve order and referential integrity.
      * Speed: ~10-15 seconds per school.
      * Estimates:1 District (5 schools) $\approx$ 1.5 minutes.10 Districts $\approx$ 15 minutes.
