import os
import time
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.types import HarmCategory, HarmBlockThreshold # Import Safety Types
from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional

# Import Rich for the progress UI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Load environment variables
load_dotenv()
api_key = os.getenv('API_KEY')
client = genai.Client(api_key=api_key)

# Initialize Rich Console
console = Console()

# ---------------------------------------------------------
# 1. Configuration & Constants
# ---------------------------------------------------------

NUM_DISTRICTS = 1

DISTRICT_NAMES = [
    "WestCharter", "EastCharter", "NorthCharter", "SouthCharter", 
    "CentralValley", "Lakeside", "MountainView", "PacificCoast"
]

# ---------------------------------------------------------
# 2. Strict Clever Schemas (Pydantic)
# ---------------------------------------------------------

GenderType = Literal['M', 'F', 'X']
GradeLevel = Literal['PK', 'KG', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
YesNo = Literal['Y', 'N']

RealisticName = Field(
    ..., 
    description="A realistic human name. MUST NOT contain numbers.", 
    pattern=r"^[^0-9]+$" 
)

class School(BaseModel):
    School_id: str
    School_name: str
    School_number: str
    State_id: Optional[str] = None
    Low_grade: GradeLevel
    High_grade: GradeLevel
    Principal: str
    Principal_email: EmailStr
    School_address: str
    School_city: str
    School_state: str
    School_zip: str
    School_phone: str

class Teacher(BaseModel):
    School_id: str
    Teacher_id: str
    Teacher_number: Optional[str] = None
    State_teacher_id: Optional[str] = None
    Teacher_email: EmailStr
    First_name: str = RealisticName
    Middle_name: Optional[str] = Field(None, pattern=r"^[^0-9]+$")
    Last_name: str = RealisticName
    Title: str

class Student(BaseModel):
    School_id: str
    Student_id: str
    Student_number: Optional[str] = None
    State_id: Optional[str] = None
    Last_name: str = RealisticName
    Middle_name: Optional[str] = Field(None, pattern=r"^[^0-9]+$")
    First_name: str = RealisticName
    Grade: GradeLevel
    Gender: GenderType
    DOB: str = Field(description="Date of birth in MM/DD/YYYY format")
    Race: Optional[str] = None
    Ell_status: Optional[YesNo] = None
    Frl_status: Optional[str] = None
    Email_address: EmailStr

class Section(BaseModel):
    School_id: str
    Section_id: str
    Teacher_id: str
    Teacher_2_id: Optional[str] = Field(None, description="Second teacher ID")
    Name: str
    Section_number: str
    Grade: GradeLevel
    Course_name: str
    Subject: str
    Period: Optional[str] = None

class Enrollment(BaseModel):
    School_id: str
    Section_id: str
    Student_id: str

class Staff(BaseModel):
    School_id: str
    Staff_id: str
    Staff_email: EmailStr
    First_name: str = RealisticName
    Last_name: str = RealisticName
    Department: str
    Title: str

class DistrictData(BaseModel):
    schools: list[School]
    teachers: list[Teacher]
    students: list[Student]
    sections: list[Section]
    enrollments: list[Enrollment]
    staff: list[Staff]

# ---------------------------------------------------------
# 3. Generator Logic (With Safety Fixes)
# ---------------------------------------------------------

def generate_district(district_index, status_spinner):
    """
    Generates data with safety settings enabled to prevent empty responses.
    """
    id_start = (district_index + 1) * 10000 
    dist_name = DISTRICT_NAMES[district_index % len(DISTRICT_NAMES)]
    email_domain = f"{dist_name.lower()}.k12.edu"
    
    prompt = f"""
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
    """
    
    # SAFETY SETTINGS: Allow all content (prevents blocking fake PII)
    safety_settings = [
        types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_NONE),
    ]

    for attempt in range(3):
        try:
            status_spinner.update(f"[bold blue]Generating {dist_name}... (Attempt {attempt+1}/3)")
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DistrictData, 
                    temperature=0.7,
                    safety_settings=safety_settings # Apply safety settings
                )
            )

            # NULL CHECK: Verify we actually got data back
            if response.parsed is None:
                # If parsed is None, the model likely blocked it or returned bad JSON
                raise ValueError("Model returned empty data (Safety block or Parse Error)")

            return response.parsed, dist_name
            
        except Exception as e:
            if "429" in str(e):
                for i in range(30, 0, -1):
                    status_spinner.update(f"[bold red]Quota limit hit. Retrying in {i}s...")
                    time.sleep(1)
            else:
                # Log error to spinner but don't crash yet
                status_spinner.update(f"[red]Error on attempt {attempt+1}: {e}. Retrying...[/red]")
                time.sleep(2) # Short pause before retry
                
    raise Exception(f"Failed to generate data for {dist_name} after 3 attempts")

# ---------------------------------------------------------
# 4. Main Execution
# ---------------------------------------------------------

def save_district_to_csv(district_data: DistrictData, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    
    def save_list(data_list, filename):
        if not data_list: return
        df = pd.DataFrame([item.model_dump(exclude_none=True) for item in data_list])
        path = os.path.join(output_folder, filename)
        df.to_csv(path, index=False)

    save_list(district_data.schools, "schools.csv")
    save_list(district_data.teachers, "teachers.csv")
    save_list(district_data.students, "students.csv")
    save_list(district_data.sections, "sections.csv")
    save_list(district_data.enrollments, "enrollments.csv")
    save_list(district_data.staff, "staff.csv")

if __name__ == "__main__":
    base_output_dir = 'school_district_data'
    
    console.rule("[bold blue]School Data Generator[/bold blue]")
    console.print(f"Target: [cyan]{NUM_DISTRICTS} Districts[/cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True 
    ) as progress:
        
        task = progress.add_task("[green]Starting...", total=NUM_DISTRICTS)

        for i in range(NUM_DISTRICTS):
            try:
                # 1. GENERATE
                district_obj, dist_name = generate_district(i, progress)
                
                # 2. SAVE
                progress.update(task, description=f"[bold yellow]Saving CSVs for {dist_name}...")
                folder_name = os.path.join(base_output_dir, f"{dist_name}_Data")
                save_district_to_csv(district_obj, folder_name)
                
                # 3. COMPLETE
                console.print(f" :white_check_mark: [bold green]{dist_name}[/bold green] Generated & Saved")
                progress.advance(task)
                
            except Exception as e:
                console.print(f" :cross_mark: [bold red]Failed District {i+1}: {e}[/bold red]")

    console.rule("[bold green]All Operations Complete[/bold green]")