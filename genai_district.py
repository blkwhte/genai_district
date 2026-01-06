import os
import datetime
import time
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.types import HarmCategory, HarmBlockThreshold
from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional, List

# Import Rich for UI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import IntPrompt, Confirm
from rich.table import Table

# Load environment variables
load_dotenv()
api_key = os.getenv('API_KEY')
client = genai.Client(api_key=api_key)
console = Console()

# ---------------------------------------------------------
# 1. Configuration (Interactive)
# ---------------------------------------------------------

console.rule("[bold blue]School Data Generator Setup[/bold blue]")

# Ask the user for inputs
NUM_DISTRICTS = IntPrompt.ask("How many [cyan]Districts[/cyan]?", default=2)
SCHOOLS_PER_DISTRICT = IntPrompt.ask("How many [cyan]Schools per District[/cyan]?", default=3)
TEACHERS_PER_SCHOOL = IntPrompt.ask("How many [cyan]Teachers per School[/cyan]?", default=5)
SECTIONS_PER_SCHOOL = IntPrompt.ask("How many [cyan]Sections per School[/cyan]?", default=4)
STUDENTS_PER_SECTION = IntPrompt.ask("How many [cyan]Students per Section[/cyan]?", default=15)
INCLUDE_CO_TEACHERS = Confirm.ask("Include [cyan]Co-Teachers[/cyan] in at least one section?", default=True)

DISTRICT_NAMES = ["WestCharter", "EastCharter", "NorthCharter", "SouthCharter", "CentralValley", "Lakeside", "MountainView", "PacificCoast"]

# Display Summary
summary_table = Table(title="Configuration Summary")
summary_table.add_column("Setting", style="cyan")
summary_table.add_column("Value", style="magenta")
summary_table.add_row("Districts", str(NUM_DISTRICTS))
summary_table.add_row("Schools/District", str(SCHOOLS_PER_DISTRICT))
summary_table.add_row("Teachers/School", str(TEACHERS_PER_SCHOOL))
summary_table.add_row("Sections/School", str(SECTIONS_PER_SCHOOL))
summary_table.add_row("Students/Section", str(STUDENTS_PER_SECTION))
summary_table.add_row("Co-Teachers", "Yes" if INCLUDE_CO_TEACHERS else "No")

console.print(summary_table)
if not Confirm.ask("Ready to generate?", default=True):
    console.print("[red]Aborted.[/red]")
    exit()

# ---------------------------------------------------------
# 2. Pydantic Models (Split into Phase 1 & Phase 2)
# ---------------------------------------------------------

GenderType = Literal['M', 'F', 'X']
GradeLevel = Literal['PK', 'KG', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
RealisticName = Field(..., pattern=r"^[^0-9]+$")

# --- PHASE 1 MODELS (Structure) ---
class School(BaseModel):
    School_id: str
    School_name: str
    School_number: str
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
    Teacher_email: EmailStr
    First_name: str = RealisticName
    Last_name: str = RealisticName
    Title: str

class Staff(BaseModel):
    School_id: str
    Staff_id: str
    Staff_email: EmailStr
    First_name: str = RealisticName
    Last_name: str = RealisticName
    Department: str
    Title: str

class DistrictStructure(BaseModel):
    schools: List[School]
    teachers: List[Teacher]
    staff: List[Staff]

# --- PHASE 2 MODELS (Rosters) ---
class Student(BaseModel):
    School_id: str
    Student_id: str
    Student_number: str
    Last_name: str = RealisticName
    First_name: str = RealisticName
    Grade: GradeLevel
    Gender: GenderType
    DOB: str
    Email_address: EmailStr

class Section(BaseModel):
    School_id: str
    Section_id: str
    Teacher_id: str
    Teacher_2_id: Optional[str] = None
    Name: str
    Grade: GradeLevel
    Subject: str

class Enrollment(BaseModel):
    School_id: str
    Section_id: str
    Student_id: str

class SchoolRoster(BaseModel):
    students: List[Student]
    sections: List[Section]
    enrollments: List[Enrollment]

# ---------------------------------------------------------
# 3. Helpers
# ---------------------------------------------------------

def get_safety_settings():
    return [
        types.SafetySetting(category=c, threshold=HarmBlockThreshold.BLOCK_NONE)
        for c in [HarmCategory.HARM_CATEGORY_HATE_SPEECH, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, 
                  HarmCategory.HARM_CATEGORY_HARASSMENT, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT]
    ]

def generate_with_retry(prompt, schema, task_id, progress, label):
    """Generic retry wrapper for API calls"""
    for attempt in range(3):
        try:
            progress.update(task_id, description=f"[blue]{label} (Attempt {attempt+1})")
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.7,
                    safety_settings=get_safety_settings()
                )
            )
            if response.parsed: return response.parsed
            
        except Exception as e:
            if "429" in str(e):
                for i in range(20, 0, -1):
                    progress.update(task_id, description=f"[red]Quota hit. Retrying in {i}s...")
                    time.sleep(1)
            else:
                time.sleep(2)
    raise Exception(f"Failed to generate {label}")

# ---------------------------------------------------------
# 4. Generators
# ---------------------------------------------------------

def generate_district_structure(dist_index, dist_name, id_start, task_id, progress):
    email_domain = f"{dist_name.lower()}.k12.edu"
    
    prompt = f"""
    Generate structure for '{dist_name} District'.
    
    REQUIREMENTS:
    - {SCHOOLS_PER_DISTRICT} Schools.
    - {TEACHERS_PER_SCHOOL} Teachers per School.
    - 2 Staff per School.
    - Include 1 extra Staff member with title "District Administrator" assigned to the first school.
    
    CONSTRAINTS:
    - IDs must start at {id_start}.
    - Emails must use @{email_domain}.
    - No placeholder names.
    """
    return generate_with_retry(prompt, DistrictStructure, task_id, progress, f"Building {dist_name} Structure")

def generate_school_roster(school: School, teachers: List[Teacher], id_start, task_id, progress):
    # Filter teachers for THIS school only
    school_teachers = [t for t in teachers if t.School_id == school.School_id]
    teacher_ids = [t.Teacher_id for t in school_teachers]
    
    co_teacher_instruction = ""
    if INCLUDE_CO_TEACHERS:
        co_teacher_instruction = "- Populate 'Teacher_2_id' for at least one section."

    # --- DOB LOGIC ---
    current_year = datetime.date.today().year
    # K-12 Students are typically 5 to 19 years old.
    # We add a 1-year buffer to be safe.
    min_birth_year = current_year - 20  # Approx 19-20 years old max
    max_birth_year = current_year - 4   # Approx 4-5 years old min
    
    prompt = f"""
    Generate roster for School: {school.School_name} (ID: {school.School_id}).
    
    REQUIREMENTS:
    - {SECTIONS_PER_SCHOOL} Sections.
    - {STUDENTS_PER_SECTION} Students per section.
    - USE THESE TEACHER IDs for sections: {teacher_ids}
    - 1 Student in each section must be enrolled in multiple sections.
    - {co_teacher_instruction}
    
    CONSTRAINTS:
    - New IDs (Student/Section) must start at {id_start}.
    - Student emails must use the school's district domain.
    - Realistic names.
    - **DOB REALISM**: Use the current year ({current_year}) as the reference. 
      Student birth years MUST be between {min_birth_year} and {max_birth_year} to match K-12 ages.
      Example: A 1st grader should be born around {current_year - 6}.
    """
    return generate_with_retry(prompt, SchoolRoster, task_id, progress, f"Rostering {school.School_name}")

# ---------------------------------------------------------
# 5. Main Execution
# ---------------------------------------------------------

if __name__ == "__main__":
    base_output_dir = 'school_district_data'
    
    # Calculate Total Operations for Progress Bar
    total_ops = NUM_DISTRICTS + (NUM_DISTRICTS * SCHOOLS_PER_DISTRICT)
    
    console.print("\n[bold green]Starting Generation Process...[/bold green]")

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), 
        BarColumn(), console=console
    ) as progress:
        
        main_task = progress.add_task("[green]Initializing...", total=total_ops)

        for i in range(NUM_DISTRICTS):
            dist_name = DISTRICT_NAMES[i % len(DISTRICT_NAMES)]
            base_id = (i + 1) * 100000 
            
            # --- PHASE 1: Structure ---
            try:
                struct = generate_district_structure(i, dist_name, base_id, main_task, progress)
                progress.advance(main_task) # Phase 1 Done
                
                # Prepare Master Lists
                all_schools = struct.schools
                all_teachers = struct.teachers
                all_staff = struct.staff
                all_students = []
                all_sections = []
                all_enrollments = []

                # --- PHASE 2: Rosters (Loop per School) ---
                for s_idx, school in enumerate(all_schools):
                    school_id_offset = base_id + ((s_idx + 1) * 10000)
                    
                    roster = generate_school_roster(school, all_teachers, school_id_offset, main_task, progress)
                    
                    all_students.extend(roster.students)
                    all_sections.extend(roster.sections)
                    all_enrollments.extend(roster.enrollments)
                    progress.advance(main_task) # One School Done

                # --- PHASE 3: Save ---
                progress.update(main_task, description=f"[yellow]Saving {dist_name}...")
                out_dir = os.path.join(base_output_dir, f"{dist_name}_Data")
                os.makedirs(out_dir, exist_ok=True)

                pd.DataFrame([x.model_dump() for x in all_schools]).to_csv(f"{out_dir}/schools.csv", index=False)
                pd.DataFrame([x.model_dump() for x in all_teachers]).to_csv(f"{out_dir}/teachers.csv", index=False)
                pd.DataFrame([x.model_dump() for x in all_staff]).to_csv(f"{out_dir}/staff.csv", index=False)
                pd.DataFrame([x.model_dump() for x in all_students]).to_csv(f"{out_dir}/students.csv", index=False)
                pd.DataFrame([x.model_dump() for x in all_sections]).to_csv(f"{out_dir}/sections.csv", index=False)
                pd.DataFrame([x.model_dump() for x in all_enrollments]).to_csv(f"{out_dir}/enrollments.csv", index=False)

                console.print(f":white_check_mark: [bold green]{dist_name} Complete[/bold green] ({len(all_students)} Students)")

            except Exception as e:
                console.print(f":cross_mark: [red]Failed {dist_name}: {e}[/red]")