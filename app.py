import sys
# Ensure console output handles UTF-8 on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from flask import Flask, render_template, request
import mysql.connector
from openai import OpenAI
import os
import json
import re
from dotenv import load_dotenv

# Load environment variables (.env file)
load_dotenv()

app = Flask(__name__)

# --- GEMINI CLIENT (via OpenAI-Compatible Endpoint) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

if not GEMINI_API_KEY:
    print("[WARNING] GEMINI_API_KEY is not configured! Please check your .env file.")

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# --- 1. HELPER: DB CONNECTION ---
def get_db_connection(db_name=None):
    config = {
        'host': os.getenv("DB_HOST", "127.0.0.1"),
        'port': int(os.getenv("DB_PORT", 3307)),
        'user': os.getenv("DB_USER", "root"),
        'password': os.getenv("DB_PASSWORD", ""),
        'use_pure': True
    }
    if db_name:
        config['database'] = db_name
    return mysql.connector.connect(**config)

# --- 2. HELPER: FETCH RULES ---
def get_rules_from_db(db_name, show_only_fixes=False):
    try:
        conn = get_db_connection(db_name)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SHOW TABLES LIKE '_project_documentation'")
        if not cursor.fetchone(): 
            conn.close()
            return []

        if show_only_fixes:
            # Fetch only newly added rules (FIXED category)
            sql = "SELECT * FROM _project_documentation WHERE category = 'BUSINESS_RULE_FIXED' ORDER BY id ASC"
        else:
            # Fetch all rules
            sql = "SELECT * FROM _project_documentation WHERE category LIKE 'BUSINESS_RULE%' ORDER BY id ASC"

        cursor.execute(sql)
        rules = cursor.fetchall()
        formatted_rules = []
        for r in rules:
            statement = r['content'].replace("RULE: ", "")
            if "REASON:" in statement: 
                statement = statement.split("REASON:")[0].strip()
            formatted_rules.append({"id": r['title'], "statement": statement})
        cursor.close()
        conn.close()
        return formatted_rules
    except Exception as e:
        print(f"   -> [DB Fetch Notice] {e}")
        return []

# --- 3. HELPER: SQL FORMATTER ---
def format_sql_for_display(raw_sql):
    if not raw_sql: return ""
    sql = raw_sql.replace("```sql", "").replace("```", "").strip()
    
    # 1. Readability improvements
    sql = re.sub(r';\s*', ';\n\n', sql)
    
    # 2. Trigger formatting
    sql = sql.replace("DELIMITER \n\n$$", "DELIMITER $$")
    sql = sql.replace("DELIMITER \n\n;", "DELIMITER ;")
    sql = sql.replace("BEGIN", "\nBEGIN")
    sql = sql.replace("END", "\nEND")
    
    return sql

# --- 4. HELPER: MERMAID CLEANER ---
def clean_mermaid_syntax(raw_mermaid):
    if not raw_mermaid: return "erDiagram"
    clean = raw_mermaid.replace("```mermaid", "").replace("mermaid", "").replace("```", "").strip()
    return clean.replace(";", "\n")

# --- 5. CORE FUNCTION: DB CREATION (WITH ERROR HANDLING) ---
def create_database(sql_script, project_data, is_fix=False):
    print("   -> [DB SETUP] Database configuration started...")
    domain_name = project_data.get('domain', 'Project').lower()
    if 'restaurant' in domain_name: target_db_name = "RestaurantDB"
    elif 'library' in domain_name: target_db_name = "LibraryDB"
    elif 'car' in domain_name: target_db_name = "CarRentalDB"
    elif 'hospital' in domain_name: target_db_name = "HospitalDB"
    elif 'hr' in domain_name: target_db_name = "HumanResourcesDB"
    else: target_db_name = "ProjectDB"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        clean_sql = sql_script.replace("```sql", "").replace("```", "").strip()

        # SQL Cleaning (for execution)
        exec_sql = re.sub(r"CREATE\s+DATABASE\s+[^;]+;", "", clean_sql, flags=re.IGNORECASE)
        exec_sql = re.sub(r"DROP\s+DATABASE\s+[^;]+;", "", exec_sql, flags=re.IGNORECASE)
        exec_sql = re.sub(r"USE\s+[^;]+;", "", exec_sql, flags=re.IGNORECASE)

        if not is_fix:
            cursor.execute(f"DROP DATABASE IF EXISTS {target_db_name}")
            cursor.execute(f"CREATE DATABASE {target_db_name}")
        cursor.execute(f"USE {target_db_name}")

        # --- CRITICAL: DISABLE FOREIGN KEY CHECKS ---
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;") 

        sql_for_python = exec_sql.replace("DELIMITER $$", "$$").replace("DELIMITER ;", "$$")
        chunks = sql_for_python.split('$$')

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk: continue
            
            if "CREATE TRIGGER" in chunk.upper():
                try:
                    safe_chunk = chunk.replace('%', '%%') 
                    cursor.execute(safe_chunk)
                    print("   -> [TRIGGER] Trigger created successfully.")
                except Exception as e:
                    print(f"   -> [TRIGGER WARNING] {e}")
            else:
                cmds = chunk.split(';')
                for cmd in cmds:
                    if cmd.strip():
                        try:
                            safe_cmd = cmd.replace('%', '%%')
                            cursor.execute(safe_cmd)
                        except Exception as e: 
                            pass

        # --- RE-ENABLE FOREIGN KEY CHECKS ---
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()

        cursor.execute(f"USE {target_db_name}")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _project_documentation (
                id INT AUTO_INCREMENT PRIMARY KEY,
                category VARCHAR(50),
                title VARCHAR(255),
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Truncate documentation if performing a fresh install
        if not is_fix:
            cursor.execute("TRUNCATE TABLE _project_documentation;")
            summary = project_data.get("project_summary", "No Summary")
            cursor.execute("INSERT INTO _project_documentation (category, title, content) VALUES (%s, %s, %s)", 
                           ("SUMMARY", "Executive Summary", summary))
        
        # Append business rules (retain old ones if in FIX mode)
        rules = project_data.get("business_rules", [])
        for rule in rules:
            raw_id = rule.get("id", "BR")
            if is_fix:
                rule_title = f"FIX UPDATE - {raw_id}"
                category = "BUSINESS_RULE_FIXED"
            else:
                rule_title = raw_id
                category = "BUSINESS_RULE"

            full_text = f"RULE: {rule.get('statement','')}\nREASON: {rule.get('rationale','')}"
            cursor.execute("INSERT INTO _project_documentation (category, title, content) VALUES (%s, %s, %s)", 
                           (category, rule_title, full_text))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"Database '{target_db_name}' Deployed Successfully! [OK]", target_db_name

    except Exception as e:
        print(f"   -> [DB NOTICE] Database connection/execution notice: {e}")
        host = os.getenv("DB_HOST", "127.0.0.1")
        port = os.getenv("DB_PORT", 3307)
        return False, f"MySQL offline at {host}:{port}", target_db_name

# --- 6. AI PROCESSING CENTER ---
def process_ai_request(form_data, extra_rule=None):
    is_fix = (extra_rule is not None)
    
    current_constraints = form_data.get('constraint', '')
    if extra_rule:
        current_constraints += f". MISSING RULE TO ADD: {extra_rule}"

    domain_val = form_data.get('domain')
    security_val = form_data.get('security', 'Admin, Staff, Customer')
    advanced_feature_val = form_data.get('advanced_feature', 'Automated state updates and audit triggers')
    reporting_val = form_data.get('reporting', 'Standard analytical and audit summaries')
    common_tasks_val = form_data.get('common_tasks', 'Create, Read, Update, Delete')

    system_prompt = "You are an Expert Database Architect. Output valid JSON ONLY without any surrounding commentary or explanations."
    
    user_inputs = f"""
    Generate a database design JSON for:
    Domain: {domain_val}
    Primary Entity: {form_data.get('primary_entity')}
    Access Control / Roles: {security_val}
    Constraints: {current_constraints}
    Automation / Triggers: {advanced_feature_val}
    Reporting Needs: {reporting_val}
    Common Operations: {common_tasks_val}
    """

    template_part = """
    --- MANDATORY RULES ---
    1. **SUMMARY**: Write a **2-PARAGRAPH** professional executive summary.
    2. **RULES**: Generate **8 to 10** distinct business rules.
    3. **TABLE DEFINITIONS (Stage 3)**: Generate FULL 'CREATE TABLE' SQL, columns and constraints.
    4. **NORMALIZATION (Stage 5)**:
       - 0NF: Comma-separated raw unnormalized data example.
       - 1NF: Split into atomic attributes/rows BUT KEEP REDUNDANT COLUMNS.
       - 2NF: Remove partial key dependencies.
       - 3NF: Remove transitive dependencies. MUST CONCEPTUALLY MATCH Stage 3 tables.
    5. **SQL**: 
       - Start with DROP/CREATE DATABASE.
       - Include ALL 'CREATE TABLE' statements.
       - Include 2 COMPLEX TRIGGERS with business logic.
       - **CRITICAL:** BEFORE every 'CREATE TRIGGER', add: 'DROP TRIGGER IF EXISTS [trigger_name];'
       - **SYNTAX:** Use 'DELIMITER $$' before triggers and '$$' after triggers. END with 'DELIMITER ;'.
       - Return ONE SINGLE SQL SCRIPT containing Tables AND Triggers together.
    6. **MERMAID**: 'erDiagram'. SHOW RELATIONSHIPS ONLY. Use underscores.

    --- OUTPUT FORMAT (STRICT JSON ONLY) ---
    {
        "project_name": "Name",
        "project_summary": "...",
        "business_rules": [{"id": "BR-1", "statement": "...", "rationale": "..."}],
        "table_definitions": [{"table_name": "...", "columns": "...", "constraints": "..."}],
        "missing_rules": [{"rule": "...", "solution": "..."}],
        "normalization_tables": [
            { "stage": "0NF", "headers": ["Raw Data"], "rows": [["1, John, NYC, Book1"]] },
            { "stage": "1NF", "headers": ["ID", "Name", "City", "Book"], "rows": [["1", "John", "NYC", "Book1"]] },
            { "stage": "2NF", "headers": ["ID", "Name", "City", "BookID"], "rows": [["1", "John", "NYC", "B1"]] },
            { "stage": "3NF", "headers": ["ID", "BookID"], "rows": [["1", "B1"]] }
        ],
        "er_diagram_mermaid": "erDiagram\\n  CUSTOMER ||--o{ ORDER : places",
        "sql_code": "CREATE TABLE..."
    }
    """

    final_prompt = user_inputs + "\n" + template_part

    try:
        models_to_try = [GEMINI_MODEL, 'gemini-flash-lite-latest', 'gemini-3.5-flash-lite']
        candidate_models = list(dict.fromkeys(models_to_try))

        response = None
        last_error = None
        for model_name in candidate_models:
            try:
                print(f"   -> [AI] Requesting design generation using {model_name}...")
                response = client.chat.completions.create(
                    model=model_name, 
                    temperature=0.2, 
                    messages=[
                        {"role": "system", "content": system_prompt}, 
                        {"role": "user", "content": final_prompt}
                    ]
                )
                print(f"   -> [AI SUCCESS] Schema generated successfully by {model_name}.")
                break
            except Exception as e:
                last_error = e
                print(f"   -> [AI WARNING] {model_name} failed ({e}). Trying fallback model...")
                import time
                time.sleep(1)

        if not response:
            raise Exception(f"All AI models exhausted. Last error: {last_error}")
            
        raw = response.choices[0].message.content
        clean = raw.replace("```json", "").replace("```", "").strip()
        if "{" in clean: 
            clean = clean[clean.find("{"):clean.rfind("}")+1]
        
        result_json = json.loads(clean)
        result_json['domain'] = domain_val

        if "er_diagram_mermaid" in result_json:
            result_json["er_diagram_mermaid"] = clean_mermaid_syntax(result_json["er_diagram_mermaid"])
            
        if "sql_code" in result_json:
            db_success, db_msg, db_name = create_database(result_json["sql_code"], result_json, is_fix=is_fix)
            
            if db_name and db_success:
                all_rules = get_rules_from_db(db_name, show_only_fixes=is_fix)
                if all_rules: 
                    result_json["business_rules"] = all_rules 
            
            disp_sql = result_json["sql_code"]
            
            if db_name:
                disp_sql = re.sub(r"CREATE\s+DATABASE\s+[^;]+;", f"CREATE DATABASE {db_name};", disp_sql, flags=re.IGNORECASE)
                disp_sql = re.sub(r"USE\s+[^;]+;", f"USE {db_name};", disp_sql, flags=re.IGNORECASE)
                if "DROP DATABASE" not in disp_sql.upper():
                    disp_sql = f"DROP DATABASE IF EXISTS {db_name};\n" + disp_sql

            result_json["sql_code"] = format_sql_for_display(disp_sql)
            result_json["db_status"] = db_msg
            result_json["db_success"] = db_success
        
        return result_json

    except Exception as e:
        print(f"[ERROR] Processing Error: {e}")
        return {"error": str(e), "db_status": f"System Error: {str(e)}", "db_success": False}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        result = process_ai_request(request.form)
        return render_template('result.html', r=result, inputs=request.form)
    return render_template('index.html')

@app.route('/fix', methods=['POST'])
def fix_rule():
    form_data = request.form.to_dict()
    result = process_ai_request(form_data, extra_rule=form_data.get('new_rule_fix'))
    return render_template('result.html', r=result, inputs=form_data)

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    print(f"[SERVER] Running on http://127.0.0.1:{port} using model '{GEMINI_MODEL}'")
    app.run(debug=True, port=port)