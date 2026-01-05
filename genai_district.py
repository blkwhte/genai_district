import json
import os
import pandas as pd
from io import StringIO
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables from .env file
load_dotenv()
api_key = os.getenv('API_KEY')

# Initialize the Client (New SDK pattern)
client = genai.Client(api_key=api_key)

# Define the prompt (Same as before)
gemini_prompt = """
Create a set of school district rostering data in CSV format according to the provided specifications. The set should include the following files: schools.csv, teachers.csv, students.csv, sections.csv, enrollments.csv, and staff.csv. The data should have the following characteristics:
- 3 Schools
- 10 Teachers per School
- 10 Staff per School
- 10 Sections per School with different grade levels
- 1 of the sections for each school should have 2 teachers
- 12 students per class
- 1 of the students in each section belongs to multiple sections in the school
- All IDs fields that are IDs or numbers must be unique
- All email addresses must be unique and realistic and use the domain "district1.net"
- No two first names across all files can be the same, must be realistic, and cannot contain numbers or special characters
- No two last names across all files can be the same, must be realistic and cannot contain numbers or special characters

Output the result as a single JSON object where the keys are the filenames (e.g., "schools.csv") and the values are the CSV content strings.

The columns for each file should include:

### schools.csv
- school_id
- school_name
- school_number
- state_id
- low_grade
- high_grade
- principal
- principal_email
- school_address
- school_city
- school_state
- school_zip
- school_phone

### teachers.csv
- school_id
- teacher_id
- teacher_number
- state_teacher_id
- teacher_email
- first_name
- middle_name
- last_name
- title

### students.csv
- school_id
- student_id
- student_number
- email_address
- state_id
- last_name
- middle_name
- first_name
- grade
- gender
- dob

### sections.csv
- school_id
- section_id
- teacher_id
- teacher_2_id
- name
- section_number
- grade

### enrollments.csv
- school_id
- section_id
- student_id

### staff.csv
- school_id
- staff_id
- staff_email
- first_name
- last_name
- department
- title
"""

print("Generating data...")

# Generate data using the new Client structure
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=gemini_prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.7
    )
)

# Extract text directly using the new SDK property
content = response.text

try:
    # Convert the JSON string to a Python dictionary
    data_dict = json.loads(content)
    
    # Directory to save CSV files
    output_dir = 'school_district_data'
    os.makedirs(output_dir, exist_ok=True)

    # Save each DataFrame to a CSV file
    for filename, csv_string in data_dict.items():
        # Clean up any potential markdown code blocks if the model added them
        if csv_string.startswith("```csv"):
            csv_string = csv_string.replace("```csv", "").replace("```", "")
            
        df = pd.read_csv(StringIO(csv_string))
        
        filepath = os.path.join(output_dir, filename)
        df.to_csv(filepath, index=False)
        print(f"Saved {filename}")

    print("All CSV files have been created and saved successfully.")

except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")
    print("Raw output:", content)
except Exception as e:
    print(f"An error occurred: {e}")