import streamlit as st
import os
import pandas as pd
import unicodedata
import re
import zipfile
import base64

# Configure the page - MUST BE FIRST
st.set_page_config(
    page_title="AIMS Directory Generator",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'students_data' not in st.session_state:
    st.session_state.students_data = []
if 'courses_data' not in st.session_state:
    st.session_state.courses_data = []
if 'workspace_created' not in st.session_state:
    st.session_state.workspace_created = False
if 'generation_results' not in st.session_state:
    st.session_state.generation_results = None

def clean_text(text):
    """Clean and normalize text by removing ALL special characters including apostrophes"""
    if pd.isna(text) or text is None or text == "":
        return ""
    
    # Convert to string
    text = str(text).strip()
    
    # Remove accents and special characters
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ASCII', 'ignore').decode('ASCII')
    
    # FIXED: Remove ALL special characters including apostrophes, only keep letters, numbers, spaces, and hyphens
    text = re.sub(r'[^a-zA-Z0-9\s\-]', '', text)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def capitalize_name(name):
    """Capitalize names properly (handle hyphens)"""
    if not name:
        return ""
    
    if '-' in name:
        return '-'.join([part.capitalize() for part in name.split('-')])
    else:
        return name.capitalize()

def parse_student_file(uploaded_file):
    """Parse student data from uploaded file - handles single column CSV"""
    students = []
    
    try:
        # Try to read as CSV first with multiple encodings
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        content = None
        
        for encoding in encodings:
            try:
                uploaded_file.seek(0)  # Reset file pointer
                content = uploaded_file.read().decode(encoding)
                st.success(f"✅ Used {encoding} encoding")
                break
            except (UnicodeDecodeError, AttributeError):
                continue
        
        if content is None:
            # Fallback to latin-1 with replacement
            uploaded_file.seek(0)
            content = uploaded_file.read().decode('latin-1', errors='replace')
            st.warning("⚠️ Used Latin-1 with character replacement")
        
        # Parse content line by line
        lines = content.splitlines()
        
        if not lines:
            st.error("❌ File is empty")
            return []
        
        # Check if first line is header
        first_line = lines[0].strip().lower()
        header_keywords = ['lastname', 'firstname', 'surname', 'name', 'nom', 'prenom', 'student']
        has_header = any(keyword in first_line for keyword in header_keywords)
        
        if has_header:
            st.info(f"📝 Skipping header: {lines[0]}")
            lines = lines[1:]  # Remove header row
        
        # Process each line
        valid_students = 0
        for line_num, line in enumerate(lines, 1 if has_header else 0):
            line = line.strip()
            if not line:
                continue
            
            # Handle single column with comma-separated names
            if ',' in line:
                # Split on the first comma only to handle "Lastname, Firstname"
                parts = line.split(',', 1)
                last_name = clean_text(parts[0])
                first_name = clean_text(parts[1]) if len(parts) > 1 else ""
                
                # Capitalize names properly
                last_name = capitalize_name(last_name)
                first_name = capitalize_name(first_name)
                
                # Validate names
                if last_name and first_name:
                    # Additional check to avoid any remaining headers
                    last_lower = last_name.lower()
                    first_lower = first_name.lower()
                    
                    if (last_lower not in header_keywords and 
                        first_lower not in header_keywords and
                        len(last_name) > 1 and len(first_name) > 1):
                        students.append((last_name, first_name))
                        valid_students += 1
                        st.write(f"👤 Line {line_num}: '{line}' → {last_name}, {first_name}")
            else:
                st.warning(f"⚠️ Line {line_num} has no comma: '{line}'")
        
        if valid_students == 0:
            st.error("❌ No valid students found. Please check your file format.")
        
        return students
        
    except Exception as e:
        st.error(f"❌ Error reading student file: {str(e)}")
        return []

def parse_course_file(uploaded_file):
    """Parse course data from uploaded file"""
    courses = []
    
    try:
        # Try multiple encodings
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        content = None
        
        for encoding in encodings:
            try:
                uploaded_file.seek(0)
                content = uploaded_file.read().decode(encoding)
                break
            except (UnicodeDecodeError, AttributeError):
                continue
        
        if content is None:
            uploaded_file.seek(0)
            content = uploaded_file.read().decode('latin-1', errors='replace')
        
        lines = content.splitlines()
        
        if not lines:
            st.error("❌ Course file is empty")
            return []
        
        # Check for header
        first_line = lines[0].strip().lower()
        header_keywords = ['course', 'coursename', 'courses', 'name', 'subject']
        has_header = any(keyword in first_line for keyword in header_keywords)
        
        if has_header:
            st.info(f"📝 Skipping course header: {lines[0]}")
            lines = lines[1:]
        
        valid_courses = 0
        for line_num, line in enumerate(lines, 1 if has_header else 0):
            original_course = line.strip()
            course = clean_text(original_course)
            
            if course and len(course) > 1:  # Minimum 2 characters
                # Capitalize course name properly
                course = ' '.join([word.capitalize() for word in course.split()])
                courses.append(course)
                valid_courses += 1
                st.write(f"📚 Line {line_num}: '{original_course}' → '{course}'")
        
        if valid_courses == 0:
            st.error("❌ No valid courses found. Please check your file format.")
        
        return courses
        
    except Exception as e:
        st.error(f"❌ Error reading course file: {str(e)}")
        return []

def parse_manual_students(student_text):
    """Parse student data from manual text input"""
    students = []
    
    if not student_text:
        return students
        
    lines = student_text.strip().split('\n')
    header_keywords = ['lastname', 'firstname', 'surname', 'name', 'nom', 'prenom']
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
            
        if ',' in line:
            # Split on the first comma only
            parts = line.split(',', 1)
            original_last = parts[0].strip()
            original_first = parts[1].strip() if len(parts) > 1 else ""
            
            last_name = clean_text(original_last)
            first_name = clean_text(original_first)
            
            # Capitalize names properly
            last_name = capitalize_name(last_name)
            first_name = capitalize_name(first_name)
            
            # Validate names
            if last_name and first_name:
                # Skip header-like entries
                last_lower = last_name.lower()
                first_lower = first_name.lower()
                
                if (last_lower not in header_keywords and 
                    first_lower not in header_keywords and
                    len(last_name) > 1 and len(first_name) > 1):
                    students.append((last_name, first_name))
                    st.write(f"👤 Line {line_num}: '{line}' → {last_name}, {first_name}")
        else:
            st.warning(f"⚠️ Line {line_num} has no comma: '{line}'")
    
    return students

def parse_manual_courses(course_text):
    """Parse course data from manual text input"""
    courses = []
    
    if not course_text:
        return courses
        
    lines = course_text.strip().split('\n')
    
    for line_num, line in enumerate(lines, 1):
        original_course = line.strip()
        course = clean_text(original_course)
        
        if course and len(course) > 1:  # Minimum 2 characters
            # Capitalize course name properly
            course = ' '.join([word.capitalize() for word in course.split()])
            courses.append(course)
            st.write(f"📚 Line {line_num}: '{original_course}' → '{course}'")
    
    return courses

def safe_makedir(path):
    """Safely create directory if it doesn't exist - returns True if created, False if already exists"""
    try:
        if os.path.exists(path):
            return False
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        st.error(f"Error creating directory {path}: {e}")
        return False

def create_readme_if_missing(path, course_name, first_name, last_name):
    """Create README.txt file if it doesn't exist - returns True if created, False if already exists"""
    try:
        readme_path = os.path.join(path, "README.txt")
        if os.path.exists(readme_path):
            return False
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(f"Course: {course_name}\nStudent: {first_name} {last_name}\n\nThis directory is for coursework and projects.")
        return True
    except Exception as e:
        st.error(f"Error creating README in {path}: {e}")
        return False

def create_directory_structure(students, courses, base_folder="AIMS-Rwanda-Workspace"):
    """Create the complete directory structure following all requirements"""
    results = {
        'students_processed': len(students),
        'students_created': 0,
        'students_skipped': 0,
        'course_folders_created': 0,
        'course_folders_skipped': 0,
        'readmes_created': 0,
        'readmes_skipped': 0,
        'base_folder': base_folder
    }
    
    # Create main working directory
    if not safe_makedir(base_folder):
        st.info(f"📁 Main directory already exists: {base_folder}")
    
    # Create structure for each student
    for last_name, first_name in students:
        # Create student folder name in format: "Lastname, Firstname"
        student_folder = f"{last_name}, {first_name}"
        student_path = os.path.join(base_folder, student_folder)
        
        # Create student directory
        if safe_makedir(student_path):
            results['students_created'] += 1
        else:
            results['students_skipped'] += 1
        
        # Create course folders for this student
        for course in courses:
            course_path = os.path.join(student_path, course)
            
            # Create course directory
            if safe_makedir(course_path):
                results['course_folders_created'] += 1
            else:
                results['course_folders_skipped'] += 1
            
            # Create README file
            if create_readme_if_missing(course_path, course, first_name, last_name):
                results['readmes_created'] += 1
            else:
                results['readmes_skipped'] += 1
    
    return results

def generate_folder_tree(start_path):
    """Generate a visual tree structure of folders"""
    if not os.path.exists(start_path):
        return "No folders generated yet."
    
    tree_lines = [f"{os.path.basename(start_path)}/"]
    
    def build_tree(current_path, prefix="", is_last=True):
        try:
            items = sorted(os.listdir(current_path))
            for i, item in enumerate(items):
                item_path = os.path.join(current_path, item)
                is_last_item = (i == len(items) - 1)
                
                if os.path.isdir(item_path):
                    tree_lines.append(f"{prefix}{'└── ' if is_last else '├── '}{item}/")
                    new_prefix = prefix + ("    " if is_last_item else "│   ")
                    build_tree(item_path, new_prefix, is_last_item)
                else:
                    tree_lines.append(f"{prefix}{'└── ' if is_last_item else '├── '}{item}")
        except Exception as e:
            tree_lines.append(f"{prefix}⚠️ Error reading: {e}")
    
    build_tree(start_path)
    return "\n".join(tree_lines)

def create_zip_download(folder_path):
    """Create a ZIP file for download"""
    try:
        zip_filename = f"{os.path.basename(folder_path)}.zip"
        
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=folder_path)
                    zipf.write(file_path, arcname)
        
        return zip_filename
    except Exception as e:
        st.error(f"Error creating ZIP file: {e}")
        return None

def main():
    # Main header
    st.markdown('<div class="main-header">📁 AIMS Rwanda Workspace Generator</div>', unsafe_allow_html=True)
    st.markdown("### **FIXED** - Proper normalization removing ALL special characters")
    
    # Sidebar navigation
    with st.sidebar:
        st.title("🎯 Navigation")
        selected_tab = st.radio(
            "Choose a section:",
            ["🏠 Home", "📤 Upload Files", "📝 Manual Input", "📊 Results", "📋 Instructions"]
        )
        
        st.markdown("---")
        st.title("Quick Actions")
        
        if st.button("🔄 Reset All Data", use_container_width=True):
            st.session_state.students_data = []
            st.session_state.courses_data = []
            st.session_state.workspace_created = False
            st.session_state.generation_results = None
            st.success("Data reset successfully!")
            st.rerun()
        
        if st.button("📋 Load Example Data", use_container_width=True):
            example_students = [
                ("Mutie", "Josiah"),
                ("Kanziga", "Belise"),
                ("Uwituze", "Djadida"),
                ("Nizeyimana", "Patrick"),
                ("Kejang", "Kutlo")
            ]
            
            example_courses = [
                "Python Programming",
                "Data Science",
                "Machine Learning",
                "Statistical Methods",
                "Research Project"
            ]
            
            st.session_state.students_data = example_students
            st.session_state.courses_data = example_courses
            st.success("📋 Example data loaded successfully!")
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Normalization Examples")
        st.info("""
        **Fixed Examples:**
        - Ng'ang'a → Nganga
        - O'nella → Onella  
        - García → Garcia
        - François → Francois
        - M'barek → Mbarek
        """)
    
    # Show selected tab content
    if selected_tab == "🏠 Home":
        show_home_page()
    elif selected_tab == "📤 Upload Files":
        show_upload_page()
    elif selected_tab == "📝 Manual Input":
        show_manual_input_page()
    elif selected_tab == "📊 Results":
        show_results_page()
    else:
        show_instructions_page()

def show_home_page():
    """Display the home page"""
    st.header("🏠 Welcome to AIMS Rwanda Workspace Generator")
    
    st.markdown("""
    <div class="info-box">
    <h4>🎯 FIXED NORMALIZATION:</h4>
    <p><strong>Now properly removes ALL special characters including apostrophes:</strong></p>
    <ul>
        <li><strong>Ng'ang'a</strong> → <strong>Nganga</strong></li>
        <li><strong>O'nella</strong> → <strong>Onella</strong></li>
        <li><strong>García-López</strong> → <strong>Garcia-Lopez</strong></li>
        <li><strong>François</strong> → <strong>Francois</strong></li>
        <li><strong>D'cruz</strong> → <strong>Dcruz</strong></li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 What This Tool Does")
        st.markdown("""
        This application automatically creates organized folder structures for:
        - **Students**: Individual folders for each student
        - **Courses**: Subfolders for each course  
        - **Organization**: README files in every course folder
        
        **Perfect for:**
        - Course administrators
        - Research project organization
        - Student workspace setup
        - Academic year preparation
        """)
    
    with col2:
        st.subheader("🚀 Quick Start")
        st.markdown("""
        1. **Go to Upload Files** or **Manual Input** tab
        2. **Provide your data** (upload or type)
        3. **Preview the data**
        4. **Generate workspace**
        5. **Download results**
        
        **Input Methods:**
        - 📤 Upload CSV files
        - 📝 Manual typing
        - 📋 Load example data
        """)
    
    # Show current status
    st.markdown("---")
    st.subheader("📈 Current Status")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.session_state.students_data:
            st.success(f"✅ {len(st.session_state.students_data)} Students Ready")
        else:
            st.warning("⚠️ No Students Loaded")
    
    with col2:
        if st.session_state.courses_data:
            st.success(f"✅ {len(st.session_state.courses_data)} Courses Ready")
        else:
            st.warning("⚠️ No Courses Loaded")
    
    with col3:
        if st.session_state.workspace_created:
            st.success("✅ Workspace Created")
        else:
            st.info("ℹ️ Ready to Generate")

def show_upload_page():
    """Display file upload page"""
    st.header("📤 Upload CSV Files")
    
    st.markdown("""
    <div class="info-box">
    <h4>🎯 FIXED NORMALIZATION:</h4>
    <p><strong>Special characters including apostrophes are now removed:</strong></p>
    <ul>
        <li>Ng'ang'a → Nganga</li>
        <li>O'nella → Onella</li>
        <li>García → Garcia</li>
        <li>D'cruz → Dcruz</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Upload Student List")
        student_file = st.file_uploader(
            "Choose student CSV file",
            type=['csv', 'txt'],
            key="student_file",
            help="Upload CSV with 'Lastname, Firstname' format, one student per line"
        )
        
        if student_file is not None:
            # Validate file
            if student_file.size == 0:
                st.error("❌ Student file is empty")
            else:
                st.info(f"📄 Uploaded: {student_file.name} ({(student_file.size/1024):.1f} KB)")
                
                with st.spinner("Reading student file..."):
                    students = parse_student_file(student_file)
                
                if students:
                    st.session_state.students_data = students
                    st.success(f"✅ Successfully loaded {len(students)} students")
                    
                    # Show preview
                    with st.expander("👀 Preview Students", expanded=True):
                        student_df = pd.DataFrame(students, columns=["Last Name", "First Name"])
                        st.dataframe(student_df, use_container_width=True)
                else:
                    st.error("❌ No valid students found in the file")
    
    with col2:
        st.subheader("Upload Course List")
        course_file = st.file_uploader(
            "Choose course CSV file", 
            type=['csv', 'txt'],
            key="course_file",
            help="Upload CSV with course names, one course per line"
        )
        
        if course_file is not None:
            # Validate file
            if course_file.size == 0:
                st.error("❌ Course file is empty")
            else:
                st.info(f"📄 Uploaded: {course_file.name} ({(course_file.size/1024):.1f} KB)")
                
                with st.spinner("Reading course file..."):
                    courses = parse_course_file(course_file)
                
                if courses:
                    st.session_state.courses_data = courses
                    st.success(f"✅ Successfully loaded {len(courses)} courses")
                    
                    # Show preview
                    with st.expander("👀 Preview Courses", expanded=True):
                        course_df = pd.DataFrame(courses, columns=["Course Name"])
                        st.dataframe(course_df, use_container_width=True)
                else:
                    st.error("❌ No valid courses found in the file")
    
    # Show generation section if we have data
    if st.session_state.students_data and st.session_state.courses_data:
        show_generation_section()

def show_manual_input_page():
    """Display manual input page"""
    st.header("📝 Manual Input")
    
    st.markdown("""
    <div class="info-box">
    <h4>🎯 FIXED NORMALIZATION:</h4>
    <p><strong>Special characters including apostrophes are now removed:</strong></p>
    <ul>
        <li>Ng'ang'a → Nganga</li>
        <li>O'nella → Onella</li>
        <li>García → Garcia</li>
        <li>D'cruz → Dcruz</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Enter Students")
        st.markdown("**Format:** `Lastname, Firstname` (one per line)")
        
        student_text = st.text_area(
            "Student list",
            height=200,
            placeholder="Mutie, Josiah\nKanziga, Belise\nNg'ang'a, John\nO'nella, Maria\nGarcía, José\nD'cruz, Anthony",
            help="Enter students in 'Lastname, Firstname' format, one per line"
        )
        
        if st.button("✅ Process Students", key="process_students", use_container_width=True):
            if student_text:
                students = parse_manual_students(student_text)
                if students:
                    st.session_state.students_data = students
                    st.success(f"✅ Processed {len(students)} students")
                    
                    # Show preview
                    with st.expander("👀 Preview Students", expanded=True):
                        student_df = pd.DataFrame(students, columns=["Last Name", "First Name"])
                        st.dataframe(student_df, use_container_width=True)
                else:
                    st.error("❌ No valid students found. Please check the format.")
            else:
                st.error("❌ Please enter some student data")
    
    with col2:
        st.subheader("Enter Courses")
        st.markdown("**Format:** Course names (one per line)")
        
        course_text = st.text_area(
            "Course list",
            height=200,
            placeholder="Python Programming\nData Science\nMachine Learning\nStatistical Methods\nResearch Project",
            help="Enter course names, one per line"
        )
        
        if st.button("✅ Process Courses", key="process_courses", use_container_width=True):
            if course_text:
                courses = parse_manual_courses(course_text)
                if courses:
                    st.session_state.courses_data = courses
                    st.success(f"✅ Processed {len(courses)} courses")
                    
                    # Show preview
                    with st.expander("👀 Preview Courses", expanded=True):
                        course_df = pd.DataFrame(courses, columns=["Course Name"])
                        st.dataframe(course_df, use_container_width=True)
                else:
                    st.error("❌ No valid courses found")
            else:
                st.error("❌ Please enter some course data")
    
    # Show generation section if we have data
    if st.session_state.students_data and st.session_state.courses_data:
        show_generation_section()

def show_generation_section():
    """Show workspace generation section"""
    st.markdown("---")
    st.header("🚀 Generate Workspace")
    
    # Configuration
    workspace_name = st.text_input(
        "Workspace Folder Name",
        value="AIMS-Rwanda-Workspace",
        help="Name of the main directory to create"
    )
    
    # Show data summary
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"📊 **Students:** {len(st.session_state.students_data)}")
    with col2:
        st.info(f"📊 **Courses:** {len(st.session_state.courses_data)}")
    
    # Generate button
    if st.button("🎯 GENERATE DIRECTORY STRUCTURE", type="primary", use_container_width=True):
        # Validate data
        if not st.session_state.students_data:
            st.error("❌ No students data available")
            return
        
        if not st.session_state.courses_data:
            st.error("❌ No courses data available")
            return
        
        # Generate workspace
        generate_workspace(workspace_name)

def generate_workspace(workspace_name):
    """Generate the workspace and show results"""
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("📋 Validating data...")
    progress_bar.progress(20)
    
    status_text.text("🏗️ Creating directory structure...")
    progress_bar.progress(60)
    
    try:
        # Create directory structure
        results = create_directory_structure(
            st.session_state.students_data,
            st.session_state.courses_data,
            workspace_name
        )
        
        status_text.text("✅ Generation complete!")
        progress_bar.progress(100)
        
        # Store results
        st.session_state.workspace_created = True
        st.session_state.generation_results = results
        
        st.success("🎉 Workspace generation completed successfully!")
        
        # Show results immediately
        show_results_content(results)
        
    except Exception as e:
        st.error(f"❌ Error during generation: {str(e)}")

def show_results_page():
    """Display results page"""
    st.header("📊 Generation Results")
    
    if st.session_state.generation_results:
        show_results_content(st.session_state.generation_results)
    else:
        st.info("ℹ️ No generation results available yet. Please generate a workspace first.")
        
        if st.session_state.students_data and st.session_state.courses_data:
            if st.button("Generate Workspace Now", type="primary"):
                generate_workspace("AIMS-Rwanda-Workspace")

def show_results_content(results):
    """Display the generation results content"""
    
    st.markdown(f"""
    <div class="success-box">
    <h3>🎉 Workspace Generation Complete!</h3>
    <p>Your directory structure has been successfully created in <strong>{results['base_folder']}</strong></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Metrics
    st.subheader("📈 Generation Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Students Processed", results['students_processed'])
    
    with col2:
        st.metric("Student Folders Created", results['students_created'])
    
    with col3:
        st.metric("Course Folders Created", results['course_folders_created'])
    
    with col4:
        st.metric("README Files Created", results['readmes_created'])
    
    # Folder structure preview
    st.subheader("📁 Folder Structure Preview")
    
    if os.path.exists(results['base_folder']):
        with st.expander("👀 View Folder Tree", expanded=True):
            folder_tree = generate_folder_tree(results['base_folder'])
            st.text(folder_tree)
    else:
        st.error("❌ Generated folder not found. Please regenerate the workspace.")
    
    # Download options
    st.subheader("📥 Download Options")
    
    if os.path.exists(results['base_folder']):
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📦 Create ZIP Download", type="secondary", use_container_width=True):
                with st.spinner("Creating ZIP archive..."):
                    zip_filename = create_zip_download(results['base_folder'])
                    if zip_filename:
                        # Create download link
                        with open(zip_filename, "rb") as f:
                            bytes_data = f.read()
                            b64 = base64.b64encode(bytes_data).decode()
                            href = f'<a href="data:application/zip;base64,{b64}" download="{zip_filename}" style="display: inline-block; padding: 10px 20px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">⬇️ Download ZIP File</a>'
                            st.markdown(href, unsafe_allow_html=True)
                            st.success("✅ ZIP file created successfully!")
        
        with col2:
            st.info(f"**Local Path:** `{os.path.abspath(results['base_folder'])}`")
    else:
        st.error("❌ Generated folder not found. Please regenerate the workspace.")

def show_instructions_page():
    """Display instructions page"""
    st.header("📋 Instructions & Requirements")
    
    st.markdown("""
    <div class="info-box">
    <h3>🎯 FIXED NORMALIZATION:</h3>
    <p><strong>Now properly removes ALL special characters including apostrophes:</strong></p>
    <ul>
        <li><strong>Ng'ang'a</strong> → <strong>Nganga</strong> (apostrophes removed)</li>
        <li><strong>O'nella</strong> → <strong>Onella</strong> (apostrophes removed)</li>
        <li><strong>García-López</strong> → <strong>Garcia-Lopez</strong> (accents removed)</li>
        <li><strong>François</strong> → <strong>Francois</strong> (accents removed)</li>
        <li><strong>D'cruz</strong> → <strong>Dcruz</strong> (apostrophes removed)</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📝 Input Format Requirements")
        
        st.markdown("""
        **Student Data Format:**
        - One student per line
        - Format: `Lastname, Firstname`
        - Example:
        ```
        Mutie, Josiah
        Kanziga, Belise
        Uwituze, Djadida
        ```
        
        **Course Data Format:**
        - One course per line
        - Just the course name
        - Example:
        ```
        Python Programming
        Data Science  
        Machine Learning
        ```
        """)
    
    with col2:
        st.subheader("🔄 File Upload Options")
        
        st.markdown("""
        **Supported File Types:**
        - CSV files (.csv)
        - Text files (.txt)
        
        **Encoding Support:**
        - UTF-8 (recommended)
        - Latin-1
        - CP1252
        - ISO-8859-1
        
        **File Structure:**
        - No complex headers needed
        - Simple one-column format
        - Automatic header detection
        """)
    
    st.markdown("---")
    st.subheader("🎯 Generated Structure")
    
    st.markdown("""
    ```
    AIMS-Rwanda-Workspace/
    ├── Mutie, Josiah/
    │   ├── Python Programming/
    │   │   └── README.txt
    │   ├── Data Science/
    │   │   └── README.txt
    │   └── Machine Learning/
    │       └── README.txt
    ├── Kanziga, Belise/
    │   ├── Python Programming/
    │   │   └── README.txt
    │   ├── Data Science/
    │   │   └── README.txt
    │   └── Machine Learning/
    │       └── README.txt
    └── ...
    ```
    """)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        st.info("Please refresh the page and try again.")
#streamlit run directories.py