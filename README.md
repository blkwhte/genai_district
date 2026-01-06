# School District Data Generation Project

This project generates a set of school district rostering data in CSV format using the Gemini API.

## Requirements

- Python 3.6 or later
- `python-dotenv` library
- `pandas` library
- `google-genai` SDK library

## Setup

1. **Clone the repository**:
    ```sh
    git clone https://github.com/blkwhte/genai_district.git
    cd <repository_directory>
    ```

2. **Create a virtual environment**:
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```
    ```
    # On Windows:
    python3 -m venv venv
    .\\venv\\Scripts\\activate
    ```

3. **Install dependencies**:
    ```sh
    pip install -r requirements.txt
    ```

4. **Create a `.env` file** with your Gemini API key:
    ```env
    API_KEY=your_gemini_api_key
    ```
You can generate an API key here: https://aistudio.google.com/app/apikey

## Usage

Run the script to generate the CSV files:

```sh
python genai_district.py
```

Temperature affects the randomness of the output, which can give better results if higher. However, it can also affect the formatting which can cause errors

Below is the current prompt being fed into the model. If you try upping the number of records per file, you may run into issues because Gemini has an output character limit, which will break the CSV generator.


# Generated Test Data Specification

### 1. Data Structure Overview
This dataset simulates a multi-district environment for Clever Rostering integration testing. Each district is contained in its own subdirectory but maintains globally unique identifiers to prevent cross-contamination during ingest.

**Directory Hierarchy:**
```text
school_district_data/
├── WestCharter_Data/      (District 1)
│   ├── schools.csv
│   ├── teachers.csv
│   ├── staff.csv
│   ├── students.csv
│   ├── sections.csv
│   └── enrollments.csv
├── EastCharter_Data/      (District 2)
│   ├── ... (same files)
└── ...
```

### 2. Identifier (ID) LogicAll IDs are integers reserved in strictly non-overlapping blocks. This guarantees that a Student ID in one district can never conflict with a Student, Teacher, or Section ID in another.

| First Header  | Second Header |
| ------------- | ------------- |
| Content Cell  | Content Cell  |
| Content Cell  | Content Cell  |

### 3. CSV Schemas & Relationships (Staff & Faculty)
The data adheres to strict referential integrity. All foreign keys (e.g., `Teacher_id` in `sections.csv`) point to valid records existing in the corresponding files.
```
#### A. schools.csv
* **Primary Key:** `School_id`
* **Logic:** 3-5 schools per district (configurable).
* **Columns:** `School_id`, `School_name`, `School_number`, `Low_grade`, `High_grade`, `Principal`, `Principal_email`, `School_address`, `School_city`, `School_state`, `School_zip`, `School_phone`

#### B. teachers.csv
* **Primary Key:** `Teacher_id`
* **Foreign Key:** `School_id`
* **Logic:** Unique email addresses per teacher.
* **Columns:** `School_id`, `Teacher_id`, `Teacher_email`, `First_name`, `Last_name`, `Title`

#### C. staff.csv
* **Primary Key:** `Staff_id`
* **Foreign Key:** `School_id`
* **Special Logic:**
    * Includes 1 "District Administrator" per district.
    * Includes 1 **Dual Role User** (a user who exists in both `teachers.csv` and `staff.csv` with the **same Email Address** but different IDs) to test multi-role merging.
* **Columns:** `School_id`, `Staff_id`, `Staff_email`, `First_name`, `Last_name`, `Department`, `Title`
```

### 4. CSV Schemas & Relationships (Rostering)

```
#### D. students.csv
* **Primary Key:** `Student_id`
* **Foreign Key:** `School_id`
* **Logic:**
    * DOBs are dynamically calculated relative to the current date (Ages 5-19).
    * Grade levels (`KG`, `1`...`12`) align with DOBs.
* **Columns:** `School_id`, `Student_id`, `Student_number`, `Last_name`, `First_name`, `Grade`, `Gender`, `DOB`, `Email_address`

#### E. sections.csv
* **Primary Key:** `Section_id`
* **Foreign Keys:** `School_id`, `Teacher_id`
* **Logic:**
    * `Teacher_id` maps to a valid teacher in `teachers.csv`.
    * Supports `Teacher_2_id` (Co-teaching) for edge-case testing.
* **Columns:** `School_id`, `Section_id`, `Teacher_id`, `Teacher_2_id`, `Name`, `Grade`, `Subject`

#### F. enrollments.csv
* **Junction Table:** Maps Students to Sections.
* **Foreign Keys:** `School_id`, `Section_id`, `Student_id`
* **Logic:** Ensures every student belongs to at least one section. Includes multi-section enrollments.
* **Columns:** `School_id`, `Section_id`, `Student_id`
```

### 5. Data Quality Standards
* **Emails:** Formatted as `user@{district_name}.k12.edu`.
* **Names:** Realistic human names (no "Student1" or "TestUser").
* **Format:** Standard CSV (Comma Separated), UTF-8 encoded.

# Limitations

###1. The "Per-School" Token Limit (The Hardest Wall)
Even though we chunk data by school, each school's roster is generated in a single API call. If a single school is too large, the JSON response will get cut off, and that specific school will fail.

* **The Limit:** ~8,192 Output Tokens (approx. 30,000 characters).

* **The Math:** A single student record in JSON takes ~150–200 characters.

* **The Cap:** You can generate roughly 150–180 students per school safely.

* ⛔ **Danger Zone:** If you set:
    * Sections per School: 10
    * Students per Section: 25
    * Total: 250 Students $\rightarrow$ **Will likely crash**.

* ✅ **Safe Zone:**
    * Sections per School: 5
    * Students per Section: 20
    * Total: 100 Students $\rightarrow$ **Safe**.

###
