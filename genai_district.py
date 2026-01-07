import os
import datetime
import time
import pandas as pd
import uuid
import random
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.types import HarmCategory, HarmBlockThreshold
from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional, List

# Import Rich for UI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import IntPrompt, Confirm, Prompt
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

# --- CONFIGURATION ---
ID_MODE = Prompt.ask(
    "Select ID Mode", 
    choices=["sequential", "alphanumeric"], 
    default="alphanumeric"
)

# Ask the user for inputs
NUM_DISTRICTS = IntPrompt.ask("How many [cyan]Districts[/cyan]?", default=2)
SCHOOLS_PER_DISTRICT = IntPrompt.ask("How many [cyan]Schools per District[/cyan]?", default=10)
TEACHERS_PER_SCHOOL = IntPrompt.ask("How many [cyan]Teachers per School[/cyan]?", default=5)
SECTIONS_PER_SCHOOL = IntPrompt.ask("How many [cyan]Sections per School[/cyan]?", default=4)
STUDENTS_PER_SECTION = IntPrompt.ask("How many [cyan]Students per Section[/cyan]?", default=15)
INCLUDE_CO_TEACHERS = Confirm.ask("Include [cyan]Co-Teachers[/cyan] in at least one section?", default=True)

# Internal Batch Size (Safe Token Limit)
BATCH_SIZE = 5 

# --- GENERIC / UNIVERSAL NAMES ---
GENERIC_DISTRICT_NAMES = [
    "MapleValley", "OakRiver", "SummitHeights", "PineCreek", 
    "LibertyUnion", "Heritage", "PioneerValley", "GrandView", 
    "Clearwater", "HopeSprings", "NorthStar", "GoldenPlains",
    "SilverLake", "WillowCreek", "Unity", "CedarRidge"
]
random.shuffle(GENERIC_DISTRICT_NAMES)

# State Mappings
STATE_MAPPINGS = {
    "C4a": ("California", "CA"),
    "T3x": ("Texas", "TX"),
    "N3y": ("New York", "NY"),
    "F1a": ("Florida", "FL"),
    "W2a": ("Washington", "WA"),
    "I1l": ("Illinois", "IL"),
    "C0l": ("Colorado", "CO"),
    "A7z": ("Arizona", "AZ"),
    "G4a": ("Georgia", "GA"),
    "M4a": ("Massachusetts", "MA")
}
STATE_KEYS = list(STATE_MAPPINGS.keys())

# Display Summary
summary_table = Table(title="Configuration Summary")
summary_table.add_column("Setting", style="cyan")
summary_table.add_column("Value", style="magenta")
summary_table.add_row("ID Mode", ID_MODE.upper())
summary_table.add_row("Districts", str(NUM_DISTRICTS))
summary_table.add_row("Schools/District", str(SCHOOLS_PER_DISTRICT))
summary_table.add_row("Teachers/School", str(TEACHERS_PER_SCHOOL))
summary_table.add_row("Students/Section", str(STUDENTS_PER_SECTION))
summary_table.add_row("Batch Size", str(BATCH_SIZE))

console.print(summary_table)
if not Confirm.ask("Ready to generate?", default=True):
    console.print("[red]Aborted.[/red]")
    exit()

# ---------------------------------------------------------
# 2. Pydantic Models
# ---------------------------------------------------------

GenderType = Literal['M', 'F', 'X']
GradeLevel = Literal['PK', 'KG', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
RealisticName = Field(..., pattern=r"^[^0-9]+$")

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
    Teacher_number: str       
    State_teacher_id: str     
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

class DistrictBatch(BaseModel):
    schools: List[School]
    teachers: List[Teacher]
    staff: List[Staff]

class Student(BaseModel):
    School_id: str
    Student_id: str
    Student_number: str 
    State_id: str             
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

def get_id_instructions(mode, state_abbr, base_id):
    if mode == "alphanumeric":
        return f"IDs must be Random HEX strings. Do NOT include State prefixes here."
    else:
        return f"IDs must be numeric and start at {base_id}."

def generate_with_retry(prompt, schema, task_id, progress, label):
    # INCREASED RETRY COUNT TO 5
    for attempt in range(5):
        try:
            progress.update(task_id, description=f"[blue]{label} (Attempt {attempt+1})")
            
            # --- API CALL ---
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
            
            # --- THROTTLE ---
            # Wait 4 seconds after every call to stay under ~15 RPM
            time.sleep(4) 
            
            if response.parsed: return response.parsed
            
        except Exception as e:
            if "429" in str(e):
                # If we hit quota, wait significantly longer (60s)
                for i in range(60, 0, -1):
                    progress.update(task_id, description=f"[red]Quota hit. Cooling down {i}s...")
                    time.sleep(1)
            else:
                time.sleep(2)
    raise Exception(f"Failed to generate {label}")

# ---------------------------------------------------------
# 4. Generators
# ---------------------------------------------------------

def generate_district_batch(dist_name, state_name, state_abbr, num_schools, id_start, task_id, progress):
    """
    Generates a small chunk of the district structure (e.g., 5 schools).
    """
    email_domain = f"{dist_name.lower()}.k12.edu"
    id_instr = get_id_instructions(ID_MODE, state_abbr, id_start)

    # --- UPDATED PROMPT: NO NUMBERED NAMES ---
    prompt = f"""
    Generate a partial structure for '{dist_name} District' located in {state_name} ({state_abbr}).
    
    REQUIREMENTS:
    - {num_schools} Schools.
    - {TEACHERS_PER_SCHOOL} Teachers per School.
    - 2 Staff per School.
    
    CONSTRAINTS:
    - {id_instr}
    - Emails must use @{email_domain}.
    
    - **LENGTH RULES**:
      1. School_id: 5-6 chars.
      2. Teacher_id & Staff_id: 7 chars.

    - **TEACHER FORMATS**:
      1. Teacher_number: 'T-[6 DIGITS]' (e.g. 'T-923456').
      2. State_teacher_id: '{state_abbr}-T-[6 Digits]' (e.g. '{state_abbr}-T-923456').

    - **NAMING RULES**:
      - Use realistic, varied names (e.g., "Pine Creek Elementary", "North High").
      - **DO NOT** include numbers or indices in names (e.g., NO "School 1", NO "Elementary 2").

    - **ANTI-PATTERN RULES**:
      - IDs must be HIGH ENTROPY.
      - NO sequential numbers/letters.
    """
    return generate_with_retry(prompt, DistrictBatch, task_id, progress, f"Building Batch ({num_schools} Schools)")

def generate_school_roster(school: School, teachers: List[Teacher], id_start, district_num_prefix, school_code_2digit, task_id, progress):
    school_teachers = [t for t in teachers if t.School_id == school.School_id]
    teacher_ids = [t.Teacher_id for t in school_teachers]
    
    co_teacher_instruction = ""
    if INCLUDE_CO_TEACHERS:
        co_teacher_instruction = "- Populate 'Teacher_2_id' for at least one section."

    current_year = datetime.date.today().year
    min_birth_year = current_year - 20 
    max_birth_year = current_year - 4 
    state_abbr = school.School_state if len(school.School_state) == 2 else "XX"
    id_instr = get_id_instructions(ID_MODE, state_abbr, id_start)

    prompt = f"""
    Generate roster for School: {school.School_name} (ID: {school.School_id}).
    
    REQUIREMENTS:
    - {SECTIONS_PER_SCHOOL} Sections.
    - {STUDENTS_PER_SECTION} Students per section.
    - USE THESE TEACHER IDs: {teacher_ids}
    - 1 Student in each section must be enrolled in multiple sections.
    - {co_teacher_instruction}
    
    CONSTRAINTS:
    - {id_instr}
    
    - **LENGTH RULES**:
      1. Student_id: 6 chars.
    
    - **STUDENT FORMATS**:
      1. Student_number: 8-digit integer starting with '{district_num_prefix}'.
      2. State_id: '{state_abbr}-{school_code_2digit}-[Student_number]'.
      
    - DOB between {min_birth_year} and {max_birth_year}.
    - **ANTI-PATTERN RULES**: NO sequential numbers/letters.
    """
    return generate_with_retry(prompt, SchoolRoster, task_id, progress, f"Rostering {school.School_name}")

# ---------------------------------------------------------
# 5. Main Execution
# ---------------------------------------------------------

if __name__ == "__main__":
    base_output_dir = 'school_district_data'
    
    # Calculate Total Operations
    # Phase 1 is now batched, but we can just estimate progress based on total schools
    total_ops = NUM_DISTRICTS + (NUM_DISTRICTS * SCHOOLS_PER_DISTRICT)
    
    console.print("\n[bold green]Starting Generation Process...[/bold green]")

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), 
        BarColumn(), console=console
    ) as progress:
        
        main_task = progress.add_task("[green]Initializing...", total=total_ops)

        for i in range(NUM_DISTRICTS):
            dist_name = GENERIC_DISTRICT_NAMES[i % len(GENERIC_DISTRICT_NAMES)]
            
            # Setup State Context
            state_key = STATE_KEYS[i % len(STATE_KEYS)]
            state_name, state_abbr = STATE_MAPPINGS[state_key]
            
            district_prefix = str(10 + i)
            base_id = (i + 1) * 100000 
            
            # --- PHASE 1: BATCHED STRUCTURE GENERATION ---
            # We must loop here to generate schools in chunks
            all_schools = []
            all_teachers = []
            all_staff = []
            
            schools_generated_count = 0
            
            while schools_generated_count < SCHOOLS_PER_DISTRICT:
                # Calculate how many to ask for in this batch
                remaining = SCHOOLS_PER_DISTRICT - schools_generated_count
                current_batch_size = min(BATCH_SIZE, remaining)
                
                # Offset IDs if using sequential mode
                batch_id_start = base_id + (schools_generated_count * 1000)
                
                try:
                    # CALL THE BATCH GENERATOR
                    batch_struct = generate_district_batch(
                        dist_name, state_name, state_abbr, 
                        current_batch_size, batch_id_start, 
                        main_task, progress
                    )
                    
                    # Accumulate results
                    all_schools.extend(batch_struct.schools)
                    all_teachers.extend(batch_struct.teachers)
                    all_staff.extend(batch_struct.staff)
                    
                    schools_generated_count += current_batch_size
                    
                except Exception as e:
                    console.print(f"[red]Batch failed for {dist_name}: {e}[/red]")
                    break # Stop district if batch fails
            
            # --- POST-PROCESSING: SINGLETONS ---
            # 1. Create District Administrator (Manually)
            # We take the first school's ID to assign them home
            if all_schools:
                admin_school_id = all_schools[0].School_id
                
                if ID_MODE == 'alphanumeric':
                    admin_id = uuid.uuid4().hex[:7]
                else:
                    admin_id = str(base_id + 99999) # Fixed high number
                
                dist_admin = Staff(
                    School_id=admin_school_id,
                    Staff_id=admin_id,
                    Staff_email=f"admin@{dist_name.lower()}.k12.edu",
                    First_name="System",
                    Last_name="Administrator",
                    Department="Central Office",
                    Title="District Administrator"
                )
                all_staff.insert(0, dist_admin)
            
            # 2. Create Dual Role User (Manually)
            if all_teachers:
                target_teacher = all_teachers[0]
                if ID_MODE == 'alphanumeric':
                    dual_id = f"{target_teacher.Teacher_id}D"[:7]
                else:
                    dual_id = str(base_id + 99998)
                
                dual_role_staff = Staff(
                    School_id=target_teacher.School_id,
                    Staff_id=dual_id,
                    Staff_email=target_teacher.Teacher_email,
                    First_name=target_teacher.First_name,
                    Last_name=target_teacher.Last_name,
                    Department="Dual Role Test",
                    Title="Teacher & Support Staff"
                )
                all_staff.append(dual_role_staff)
            
            progress.advance(main_task) # Phase 1 Done
            
            # --- PHASE 2: ROSTERING ---
            all_students = []
            all_sections = []
            all_enrollments = []

            for s_idx, school in enumerate(all_schools):
                school_id_offset = base_id + ((s_idx + 1) * 10000)
                school_code_2digit = f"{s_idx + 1:02d}"

                try:
                    roster = generate_school_roster(
                        school, 
                        all_teachers, 
                        school_id_offset, 
                        district_prefix,
                        school_code_2digit, 
                        main_task, 
                        progress
                    )
                    
                    all_students.extend(roster.students)
                    all_sections.extend(roster.sections)
                    all_enrollments.extend(roster.enrollments)
                    progress.advance(main_task)
                except Exception as e:
                     console.print(f"[red]Rostering failed for {school.School_name}: {e}[/red]")


            # --- PHASE 3: SAVE ---
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