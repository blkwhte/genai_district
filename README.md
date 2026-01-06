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

Generate a realistic school district dataset for '{dist_name} District'.
    
    DATA SPECIFICATIONS:
    - 5 Schools (Mix of Elementary, Middle, High).
    - 5 Teachers per School.
    - 2 Staff per School.
    - 5 Sections per School.
    - 10 Students per Section.
    - At least 1 section per school should have a 'Teacher_2_id' populated.
    - 1 Student in each section should belong to multiple sections.
    
    CRITICAL QUALITY CONTROLS:
    - **NO PLACEHOLDER NAMES**: Names like "Teacher1" or "Lname4" are FORBIDDEN.
    - **DOMAIN**: All emails MUST use the domain @{email_domain}.
    - **IDS**: All IDs MUST be integers starting at {id_start}.
    
    Output must strictly adhere to the JSON schema provided.
