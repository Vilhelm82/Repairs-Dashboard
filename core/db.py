from datetime import datetime  # Add at the top of db.py
import sqlite3
import logging
import re


logger = logging.getLogger(__name__)
DB_NAME = "jobs.db"

def init_db():
    """Initializes the database, creating all necessary tables and adding new columns if they don't exist."""
    logger.info(f"[DB] Initializing database: {DB_NAME}")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # --- Create Customers Table ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_no TEXT NOT NULL UNIQUE,
            customer_name TEXT,
            general_notes TEXT
        )
    """)
    logger.info("[DB] Customers table created or verified.")

    # --- Create Tags Tables for Searching ---
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT NOT NULL UNIQUE
            )
        """)
        logger.info("[DB] Tags table created or verified.")

        # Verify the tags table exists by trying to insert a test tag
        cur.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES ('test_tag')")
        conn.commit()
        logger.info("[DB] Test tag inserted to verify tags table.")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_tags (
                job_ref TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                FOREIGN KEY(job_ref) REFERENCES jobs(job_ref),
                FOREIGN KEY(tag_id) REFERENCES tags(tag_id),
                PRIMARY KEY (job_ref, tag_id)
            )
        """)
        logger.info("[DB] Job_tags table created or verified.")
    except Exception as e:
        logger.error(f"[DB] Error creating tags tables: {e}")
        raise
    # --- NEW: Create Events Table for Job History/Diary ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_ref TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_description TEXT,
            FOREIGN KEY(job_ref) REFERENCES jobs(job_ref)
        )
    """)

    # --- Ensure Jobs Table is Up-to-Date ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_ref TEXT PRIMARY KEY,
            customer_no TEXT,
            customer_name TEXT,
            job_date TEXT,
            description TEXT,
            job_class_cond TEXT,
            overview_status TEXT 
        )
    """)

    # Add new columns to the jobs table for backward compatibility
    try:
        cur.execute("ALTER TABLE jobs ADD COLUMN customer_id INTEGER REFERENCES customers(id)")
    except sqlite3.OperationalError:
        pass # Column already exists
    try:
        cur.execute("ALTER TABLE jobs ADD COLUMN parts_ordered_date TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists
    try:
        cur.execute("ALTER TABLE jobs ADD COLUMN tool_subject TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists
        # Inside the init_db function
    try:
        cur.execute("ALTER TABLE jobs ADD COLUMN booking_date TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()
    conn.close()
    logger.info("[DB] Database initialized successfully.")

def insert_job(data):
    """
    Inserts or replaces a job and its associated customer into the database.
    This function is now responsible for handling the customer-job relationship.
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    customer_no = data.get("customer_no")
    customer_name = data.get("customer_name")
    job_ref = data.get("job_ref")

    customer_id = None
    if customer_no:
        # Step 1: Insert the customer if they don't exist, otherwise do nothing.
        cur.execute("INSERT OR IGNORE INTO customers (customer_no, customer_name) VALUES (?, ?)", (customer_no, customer_name))

        # Step 2: Get the unique internal ID for that customer.
        cur.execute("SELECT id FROM customers WHERE customer_no = ?", (customer_no,))
        result = cur.fetchone()
        if result:
            customer_id = result[0]

    # Step 3: Determine the overview_status for the job.
    job_class = data.get("Job_Class_Cond", "")
    tool_subject = data.get("tool_subject", "").lower()
    overview_status = ""

    # Check tool subject first for special categories
    if tool_subject == "battery":
        overview_status = "Batteries Under Eval"
    elif tool_subject == "milwaukee":
        overview_status = "Milwaukee Warranty"
    # Then check job class for standard categories
    elif job_class == "Warranty Jobs":
        overview_status = "Open Warranties"
    elif job_class == "Workshop Job":
        overview_status = "Open Quote To Repair"

    # Step 4: Insert or Replace the job with the customer_id link and new tool_subject.
    sql = """
        INSERT OR REPLACE INTO jobs (
            job_ref, customer_no, customer_name, job_date, description, 
            job_class_cond, overview_status, customer_id, tool_subject
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        job_ref,
        customer_no,
        customer_name,
        data.get("date"),
        "\n".join(data.get("descriptions", [])),
        job_class,
        overview_status,
        customer_id,
        data.get("tool_subject", "Uncategorized") # Add the new field
    )
    cur.execute(sql, params)
    conn.commit()
    conn.close()
    logger.info(f"[DB] Successfully inserted/updated job: {job_ref}")

def get_job_by_ref(job_ref):
    """Retrieves a single job's data as a dictionary."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE job_ref = ?", (job_ref,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    job_data = dict(row)
    job_data['descriptions'] = job_data['description'].split('\n') if job_data.get('description') else []
    return job_data

def get_all_jobs(full=False):
    """
    Fetches job references. If full=True, returns a list of dictionaries.
    """
    conn = sqlite3.connect(DB_NAME)
    if full:
        conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs ORDER BY job_ref")
    jobs = [dict(row) for row in cur.fetchall()] if full else [row[0] for row in cur.fetchall()]
    conn.close()
    return jobs

# --- NEW FUNCTIONS FOR THE OVERHAULED UI ---

def update_job_description(job_ref: str, new_description: str):
    """Updates the entire description field for a given job."""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE jobs SET description = ? WHERE job_ref = ?", (new_description, job_ref))
        conn.commit()
        logger.info(f"[DB] Updated description for job {job_ref}")

STATUS_MAPPING = {
    "waiting on parts": "Waiting on Parts",
    "waiting on customer": "Waiting on Customer/Quote",
    "waiting on customer/quote": "Waiting on Customer/Quote",
    "open warranties": "Open Warranties",
    "open quote to repair": "Open Quote To Repair",
    "jobs completed": "Jobs Completed",
    "batteries under eval": "Batteries Under Eval",
    "outsourced jobs": "Outsourced Jobs",
    "milwaukee warranty": "Milwaukee Warranty",
    "miscellaneous": "Miscellaneous"
}

def standardize_status(status: str) -> str:
    """Ensure consistent status strings throughout the application"""
    standardized = STATUS_MAPPING.get(status.lower(), status)
    print(f"Debug - Standardizing status: '{status}' -> '{standardized}'")  # Debug line
    return standardized

def update_job_status(job_ref: str, new_status: str, parts_ordered_date: str = None):
    """Updates the overview_status and optionally the parts_ordered_date for a job."""
    # Standardize the status before saving
    standardized_status = standardize_status(new_status)
    current_date = datetime.now().strftime("%Y-%m-%d")

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()

        # First update the job status with standardized status
        if parts_ordered_date:
            cur.execute("""
                UPDATE jobs 
                SET overview_status = ?, 
                    parts_ordered_date = ? 
                WHERE job_ref = ?
            """, (standardized_status, parts_ordered_date, job_ref))
        else:
            cur.execute("""
                UPDATE jobs 
                SET overview_status = ? 
                WHERE job_ref = ?
            """, (standardized_status, job_ref))

        # Then create an event for this status change
        event_description = f"Status changed to: {new_status}"
        if parts_ordered_date:
            event_description += f" (Parts ordered on: {parts_ordered_date})"

        cur.execute("""
            INSERT INTO events 
            (job_ref, event_date, event_type, event_description) 
            VALUES (?, ?, ?, ?)
        """, (job_ref, current_date, standardized_status, event_description))

        conn.commit()

    # Add debug inspection here
    inspect_job_status(job_ref)
    logger.info(f"[DB] Updated status for job {job_ref} to '{new_status}'")

def get_customer_by_job_ref(job_ref: str):
    """Finds the customer associated with a given job reference."""
    job = get_job_by_ref(job_ref)
    if not job or not job.get('customer_id'):
        return None

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers WHERE id = ?", (job['customer_id'],))
        customer_data = cur.fetchone()
        return dict(customer_data) if customer_data else None

def get_jobs_by_customer_id(customer_id: int):
    """Retrieves all jobs for a given internal customer ID."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE customer_id = ? ORDER BY job_date DESC", (customer_id,))
        jobs = [dict(row) for row in cur.fetchall()]
        return jobs
def search_jobs(search_term: str, filters: list):
    """
    Searches for jobs based on a search term and a list of status filters.
    The search term is checked against job_ref, customer_no, customer_name, tool_subject,
    description, and job_class_cond.
    Uses full word search to match complete words rather than partial matches.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Base query - include all relevant fields in the SELECT statement
    query = """SELECT job_ref, customer_no, customer_name, tool_subject, job_date, 
               description, job_class_cond, overview_status, parts_ordered_date 
               FROM jobs WHERE 1=1"""
    params = []

    # Add search term condition if provided
    if search_term:
        # For full word search, we need to match:
        # 1. Exact match (field = search_term)
        # 2. Word at the beginning followed by space (field LIKE 'search_term %')
        # 3. Word at the end preceded by space (field LIKE '% search_term')
        # 4. Word in the middle surrounded by spaces (field LIKE '% search_term %')
        query += """ AND (
                    job_ref = ? OR job_ref LIKE ? OR job_ref LIKE ? OR job_ref LIKE ? OR
                    customer_no = ? OR customer_no LIKE ? OR customer_no LIKE ? OR customer_no LIKE ? OR
                    customer_name = ? OR customer_name LIKE ? OR customer_name LIKE ? OR customer_name LIKE ? OR
                    tool_subject = ? OR tool_subject LIKE ? OR tool_subject LIKE ? OR tool_subject LIKE ? OR
                    description = ? OR description LIKE ? OR description LIKE ? OR description LIKE ? OR
                    job_class_cond = ? OR job_class_cond LIKE ? OR job_class_cond LIKE ? OR job_class_cond LIKE ?
                )"""

        # Parameters for each field (exact, start, end, middle)
        exact_term = search_term
        start_term = f"{search_term} %"
        end_term = f"% {search_term}"
        middle_term = f"% {search_term} %"

        # Add all parameters for each field
        for _ in range(6):  # Six fields: job_ref, customer_no, customer_name, tool_subject, description, job_class_cond
            params.extend([exact_term, start_term, end_term, middle_term])

    # Add status filter conditions if any are provided
    if filters:
        # Creates a string of placeholders, e.g., (?, ?, ?)
        placeholders = ', '.join('?' for _ in filters)
        query += f" AND overview_status IN ({placeholders})"
        params.extend(filters)

    query += " ORDER BY job_date DESC"

    cur.execute(query, params)
    results = [dict(row) for row in cur.fetchall()]
    conn.close()
    return results
def get_all_tags():
    """Retrieves all unique tag names from the database."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()

            # First check if the tags table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tags'")
            if not cur.fetchone():
                logger.warning("[DB] Tags table does not exist. Initializing database.")
                init_db()  # Initialize the database if the tags table doesn't exist

            # Now try to get the tags
            cur.execute("SELECT tag_name FROM tags ORDER BY tag_name")
            # Fetch all rows and unpack the single-item tuples into a simple list
            tags = [row[0] for row in cur.fetchall()]
        logger.info(f"[DB] Retrieved {len(tags)} tags from the database.")
        return tags
    except sqlite3.OperationalError as e:
        logger.error(f"[DB] Error retrieving tags: {e}")
        # If there's still an error, initialize the database and return an empty list
        init_db()
        return []


def add_tag(tag_name: str):
    """Adds a new tag to the tags table if it doesn't already exist."""
    tag_to_add = tag_name.strip()
    if not tag_to_add:
        return  # Do not add empty tags

    try:
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()

            # First check if the tags table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tags'")
            if not cur.fetchone():
                logger.warning("[DB] Tags table does not exist when adding tag. Initializing database.")
                init_db()  # Initialize the database if the tags table doesn't exist

            # INSERT OR IGNORE will do nothing if the tag_name (which is UNIQUE) already exists.
            cur.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES (?)", (tag_to_add,))
            conn.commit()
        logger.info(f"[DB] Added tag: '{tag_to_add}' (if it didn't already exist).")
    except sqlite3.OperationalError as e:
        logger.error(f"[DB] Error adding tag '{tag_to_add}': {e}")
        # If there's an error, try to initialize the database
        init_db()
        # Try again after initializing
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES (?)", (tag_to_add,))
            conn.commit()
        logger.info(f"[DB] Added tag after database initialization: '{tag_to_add}'.")


def delete_tag(tag_name: str):
    """Deletes a tag and any of its associations with jobs."""
    tag_to_delete = tag_name.strip()
    if not tag_to_delete:
        return

    try:
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()

            # First check if the tags table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tags'")
            if not cur.fetchone():
                logger.warning("[DB] Tags table does not exist when deleting tag. Initializing database.")
                init_db()  # Initialize the database if the tags table doesn't exist
                return  # No need to try to delete from a newly created table

            # First, find the ID of the tag to be deleted
            cur.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (tag_to_delete,))
            result = cur.fetchone()

            if result:
                tag_id_to_delete = result[0]

                # Check if job_tags table exists
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='job_tags'")
                if cur.fetchone():
                    # Delete all associations from the junction table
                    cur.execute("DELETE FROM job_tags WHERE tag_id = ?", (tag_id_to_delete,))

                # Finally, delete the tag itself
                cur.execute("DELETE FROM tags WHERE tag_id = ?", (tag_id_to_delete,))
                conn.commit()
                logger.info(f"[DB] Deleted tag '{tag_to_delete}' and its associations.")
            else:
                logger.warning(f"[DB] Attempted to delete tag '{tag_to_delete}', but it was not found.")
    except sqlite3.OperationalError as e:
        logger.error(f"[DB] Error deleting tag '{tag_to_delete}': {e}")
        # If there's an error, try to initialize the database
        init_db()

def update_job_record(job_ref: str, new_data: dict):
        """
        Updates all fields for a specific job record in the database.
        This performs a targeted UPDATE, not a full replace.
        """
        # The fields must be in the correct order for the SQL statement
        sql = """
              UPDATE jobs SET 
                  customer_no     = ?, 
                  customer_name   = ?, 
                  job_date        = ?, 
                  description     = ?, 
                  job_class_cond  = ?, 
                  overview_status = ?, 
                  tool_subject    = ?
              WHERE job_ref = ? 
              """
        params = (
            new_data.get("customer_no", ""),
            new_data.get("customer_name", ""),
            new_data.get("job_date", ""),
            new_data.get("description", ""),
            new_data.get("job_class_cond", ""),
            new_data.get("overview_status", ""),
            new_data.get("tool_subject", ""),
            job_ref  # The WHERE clause parameter
        )

        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()

        # Add an event for the job update to ensure it appears in the calendar
        event_type = new_data.get("overview_status", "Job Updated")
        add_job_event(job_ref, event_type, f"Job record updated")

        logger.info(f"[DB] Successfully updated full record for job: {job_ref}")

def add_job_event(job_ref: str, event_type: str, description: str = ""):
    """Adds a new event for a specific job to the events diary."""
    event_date = datetime.now().strftime("%Y-%m-%d") # Use a consistent YYYY-MM-DD format
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO events (job_ref, event_date, event_type, event_description) VALUES (?, ?, ?, ?)",
            (job_ref, event_date, event_type, description)
        )
        conn.commit()
    logger.info(f"[DB] Logged event '{event_type}' for job {job_ref}.")

    # Refresh the calendar if it exists
    try:
        # Get the app instance from the registry
        import app_registry
        app = app_registry.get_app()
        if app and hasattr(app, 'refresh_calendar'):
            app.refresh_calendar()
            logger.info(f"[DB] Refreshed calendar after adding event for {job_ref}.")
    except Exception as e:
        logger.debug(f"[DB] Could not refresh calendar: {e}")

def get_events_for_date(target_date: str):
    """Retrieves all events for a specific date (YYYY-MM-DD)."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM events WHERE event_date = ? ORDER BY job_ref", (target_date,))
        events = [dict(row) for row in cur.fetchall()]
    return events

def get_events_between_dates(start_date, end_date):
    """
    Retrieves all events between two dates (inclusive).

    Args:
        start_date (datetime): Start date to search from
        end_date (datetime): End date to search to

    Returns:
        list: List of event dictionaries
    """
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Convert datetime objects to string format YYYY-MM-DD
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        cur.execute("""
            SELECT *, date(event_date) as date 
            FROM events 
            WHERE date(event_date) >= date(?) 
            AND date(event_date) < date(?)
            ORDER BY event_date
        """, (start_str, end_str))

        events = [dict(row) for row in cur.fetchall()]
        return events

# Add to db.py

# This function is a duplicate of the one at the top of the file
# and has been removed to prevent conflicts

def inspect_job_status(job_ref: str = None):
    """Debug function to inspect job statuses in the database."""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        if job_ref:
            cur.execute("""
                SELECT job_ref, overview_status, parts_ordered_date 
                FROM jobs 
                WHERE job_ref = ?
            """, (job_ref,))
            rows = cur.fetchall()
        else:
            cur.execute("""
                SELECT job_ref, overview_status, parts_ordered_date 
                FROM jobs 
                WHERE overview_status LIKE '%wait%' OR overview_status LIKE '%Wait%'
            """)
            rows = cur.fetchall()

        print("\nDatabase Status Inspection:")
        for row in rows:
            print(f"Job: {row[0]}, Status: '{row[1]}', Parts Ordered: {row[2]}")

def add_backlog_event(job_ref: str, event_date: str, event_type: str = None, description: str = ""):
    """
    Adds a backlog event for a specific job with a specified date.
    This allows populating the calendar with historical events.

    Args:
        job_ref (str): The job reference number
        event_date (str): The date for the event in YYYY-MM-DD format
        event_type (str, optional): The type of event. If None, uses the job's current status
        description (str, optional): A description for the event
    """
    # If no event type is provided, use the job's current status
    if event_type is None:
        job_data = get_job_by_ref(job_ref)
        if job_data:
            event_type = job_data.get('overview_status', 'Job Imported')
        else:
            event_type = 'Job Imported'

    # Validate date format
    try:
        datetime.strptime(event_date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"[DB] Invalid date format for backlog event: {event_date}. Use YYYY-MM-DD format.")
        return False

    # Add the event
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO events (job_ref, event_date, event_type, event_description) VALUES (?, ?, ?, ?)",
            (job_ref, event_date, event_type, description)
        )
        conn.commit()
    logger.info(f"[DB] Logged backlog event '{event_type}' for job {job_ref} on date {event_date}.")

    # Refresh the calendar if it exists
    try:
        # Get the app instance from the registry
        import app_registry
        app = app_registry.get_app()
        if app and hasattr(app, 'refresh_calendar'):
            app.refresh_calendar()
            logger.info(f"[DB] Refreshed calendar after adding backlog event for {job_ref}.")
    except Exception as e:
        logger.debug(f"[DB] Could not refresh calendar: {e}")

    return True

def update_customer_notes(customer_id: int, notes: str):
    """Updates the general_notes field for a specific customer."""
    if not customer_id:
        logger.warning("[DB] Cannot update notes: No customer ID provided")
        return False

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE customers SET general_notes = ? WHERE id = ?",
            (notes, customer_id)
        )
        conn.commit()
    logger.info(f"[DB] Updated general notes for customer ID: {customer_id}")
    return True

def delete_job(job_ref: str):
    """
    Deletes a job and all its associated records from the database.

    Args:
        job_ref (str): The job reference number to delete

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()

            # First delete any events associated with the job
            cur.execute("DELETE FROM events WHERE job_ref = ?", (job_ref,))
            events_deleted = cur.rowcount

            # Then delete any job_tags associations
            cur.execute("DELETE FROM job_tags WHERE job_ref = ?", (job_ref,))
            tags_deleted = cur.rowcount

            # Finally delete the job itself
            cur.execute("DELETE FROM jobs WHERE job_ref = ?", (job_ref,))
            job_deleted = cur.rowcount

            conn.commit()

        logger.info(f"[DB] Deleted job {job_ref} with {events_deleted} events and {tags_deleted} tag associations")
        return True
    except Exception as e:
        logger.error(f"[DB] Error deleting job {job_ref}: {e}")
        return False

def fix_database_records():
    """One-time fix for status case and character whitelist in existing records"""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()

        # Fix status cases
        status_map = {
            "waiting on parts": "Waiting on Parts",
            "waiting on customer": "Waiting on Customer/Quote",
            "waiting on customer/quote": "Waiting on Customer/Quote",
            "open warranties": "Open Warranties",
            "open quote to repair": "Open Quote To Repair",
            "jobs completed": "Jobs Completed"
        }

        # Get all distinct statuses
        cur.execute("SELECT DISTINCT overview_status FROM jobs WHERE overview_status IS NOT NULL")
        statuses = cur.fetchall()

        # Update each status to its standardized form
        for (status,) in statuses:
            standardized = status_map.get(status.lower(), status)
            if standardized != status:
                cur.execute("""
                    UPDATE jobs 
                    SET overview_status = ? 
                    WHERE overview_status = ?
                """, (standardized, status))
                print(f"Updated status from '{status}' to '{standardized}'")

        # Fix job reference characters
        cur.execute("SELECT job_ref FROM jobs")
        jobs = cur.fetchall()
        for (job_ref,) in jobs:
            # Remove any characters that aren't alphanumeric
            cleaned_ref = re.sub(r'[^A-Za-z0-9]', '', job_ref)
            if cleaned_ref != job_ref:
                cur.execute("""
                    UPDATE jobs 
                    SET job_ref = ? 
                    WHERE job_ref = ?
                """, (cleaned_ref, job_ref))
                print(f"Cleaned job reference from '{job_ref}' to '{cleaned_ref}'")

        conn.commit()
        print("Database cleanup completed")

def find_and_remove_stray_records():
    """
    Finds and removes stray records with empty job references from the database.
    Specifically targets records from June 3, 2025.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()

        # Check for stray records in the events table
        cur.execute("""
            SELECT event_id, job_ref, event_date, event_type, event_description 
            FROM events 
            WHERE job_ref = '' OR job_ref IS NULL
        """)
        stray_events = cur.fetchall()

        if stray_events:
            print(f"Found {len(stray_events)} stray records in events table:")
            for event in stray_events:
                print(f"  Event ID: {event[0]}, Job Ref: '{event[1]}', Date: {event[2]}, Type: {event[3]}")

                # Check if this is the specific June 3, 2025 record
                if "03" in str(event[2]) and ("JUN" in str(event[2]) or "june" in str(event[2]).lower()) and "25" in str(event[2]):
                    print(f"  This appears to be the stray record from June 3, 2025. Deleting...")
                    cur.execute("DELETE FROM events WHERE event_id = ?", (event[0],))
                    print(f"  Deleted event ID {event[0]}")
        else:
            print("No stray records found in events table.")

        # Check for stray records in the job_tags table
        cur.execute("""
            SELECT job_ref, tag_id 
            FROM job_tags 
            WHERE job_ref = '' OR job_ref IS NULL
        """)
        stray_job_tags = cur.fetchall()

        if stray_job_tags:
            print(f"Found {len(stray_job_tags)} stray records in job_tags table:")
            for job_tag in stray_job_tags:
                print(f"  Job Ref: '{job_tag[0]}', Tag ID: {job_tag[1]}")
                cur.execute("DELETE FROM job_tags WHERE job_ref = ? AND tag_id = ?", (job_tag[0], job_tag[1]))
                print(f"  Deleted job_tag with Tag ID {job_tag[1]}")
        else:
            print("No stray records found in job_tags table.")

        # Check for any other stray records in the jobs table (unlikely due to PRIMARY KEY constraint)
        cur.execute("""
            SELECT job_ref, job_date 
            FROM jobs 
            WHERE job_ref = '' OR job_ref IS NULL
        """)
        stray_jobs = cur.fetchall()

        if stray_jobs:
            print(f"Found {len(stray_jobs)} stray records in jobs table (unusual):")
            for job in stray_jobs:
                print(f"  Job Ref: '{job[0]}', Date: {job[1]}")
                if job[1] and "03" in str(job[1]) and ("JUN" in str(job[1]) or "june" in str(job[1]).lower()) and "25" in str(job[1]):
                    print(f"  This appears to be the stray record from June 3, 2025. Deleting...")
                    cur.execute("DELETE FROM jobs WHERE job_ref = ?", (job[0],))
                    print(f"  Deleted job with empty reference")
        else:
            print("No stray records found in jobs table (as expected).")

        conn.commit()
        print("Stray record check and cleanup completed")
