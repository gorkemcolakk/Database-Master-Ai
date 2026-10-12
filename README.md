# 🏛️ Database Master AI
### Automated Database Architect & Normalization Engine powered by Google Gemini

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-black.svg)](https://flask.palletsprojects.com/)
[![LLM Engine](https://img.shields.io/badge/AI%20Engine-Google%20Gemini-orange.svg)](https://ai.google.dev/)
[![Database](https://img.shields.io/badge/RDBMS-MySQL-00758F.svg)](https://www.mysql.com/)
[![Diagrams](https://img.shields.io/badge/ERD-Mermaid.js-ff69b4.svg)](https://mermaid.js.org/)

**Database Master AI** is an intelligent, full-lifecycle database engineering assistant. Given high-level domain requirements, entity constraints, or business rules, it synthesizes an entire enterprise-grade relational database architecture across a 7-stage pipeline—from requirements engineering and normal form decomposition (0NF through 3NF) to interactive gap analysis and executable MySQL DDL with triggers.

---

## ✨ Key Features

- **⚡ End-to-End 7-Stage Architecture Generation:**
  1. **Executive Summary:** Professional overview and scope definition of the system.
  2. **Business Rules (BRs):** 8–10 strict operational constraints with business rationales.
  3. **Table Schema Definitions:** Detailed columns, primary/foreign keys, and data types.
  4. **Interactive Gap Analysis ("FIX IT" Loop):** Identifies missing edge-case constraints and allows one-click iterative schema refinement.
  5. **Step-by-Step Normalization (0NF → 3NF):** Tabular proof of functional dependency elimination from unnormalized raw data to Third Normal Form.
  6. **Interactive Entity Relationship Diagram (ERD):** Dynamic relational diagrams rendered live in the browser using Mermaid.js.
  7. **Production-Ready MySQL Scripts:** Full DDL script including schema creation, complex business triggers, and foreign key integrity management.
- **🔄 Dual Operation Mode (Live Deployment vs. Preview Mode):**
  - **Live Mode:** Automatically connects to your local MySQL instance, creates the database, configures triggers, and generates a persistent `_project_documentation` metadata table.
  - **Preview Mode (Fallback):** Generates and displays full architectural artifacts without requiring a running MySQL server.
- **🎨 Modern Dark Dashboard & One-Click PDF Export:** Sleek UI built with preset templates (Car Rental, Restaurant POS, Hospital Management, HR, Library) and direct PDF export capability.

---

## 🛠️ Tech Stack

- **Backend:** Python 3, Flask
- **AI / LLM Integration:** Google Gemini (`gemini-flash-latest`) via OpenAI-compatible endpoint
- **RDBMS:** MySQL Connector (`mysql-connector-python`)
- **Frontend:** Vanilla HTML5, Modern CSS (Glassmorphism / Charcoal & Amber theme), Mermaid.js
- **Environment Management:** `python-dotenv`

---

## 🚀 Quick Start

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/<your-username>/database-master-ai.git
cd database-master-ai

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Open `.env` and insert your [Google AI Studio API Key](https://aistudio.google.com/):
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-flash-latest

# MySQL Database Settings (Optional for Live Mode)
DB_HOST=127.0.0.1
DB_PORT=3307
DB_USER=root
DB_PASSWORD=
```

### 4. Run the Application
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 📂 Project Structure

```text
├── app.py                     # Main Flask application & Gemini LLM agent pipeline
├── requirements.txt           # Python package dependencies
├── .env.example               # Environment variables template
├── .gitignore                 # Prevents secrets (.env) and cache leaks
├── README.md                  # Project documentation & guides
└── templates/
    ├── index.html             # Dashboard with scenario cards & configuration form
    └── result.html            # 7-Stage Architectural Report & Interactive ERD viewer
```

---

## 🛡️ Security & Best Practices

- **Zero Secret Leaks:** All API credentials and database passwords are managed exclusively through environment variables (`.env`) and excluded from Git history via `.gitignore`.
- **Foreign Key Safety:** Automated MySQL execution temporarily disables and safely re-enables `FOREIGN_KEY_CHECKS` during batch table and trigger migrations.
- **Graceful Error Handling:** Console logging is normalized for cross-platform Unicode and CP1254/Windows-ANSI compatibility.

---

## 📄 License
This project was developed as a Database Systems project and is licensed under the [MIT License](LICENSE).
