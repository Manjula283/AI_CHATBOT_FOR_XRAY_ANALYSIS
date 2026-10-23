# ThoraxAI Clinical Workspace — AI Chest X-ray Analysis Chatbot 

An English-only AI-powered web application built with **Python, Flask, SQLAlchemy ORM (MySQL 8.0+ / SQLite), OpenCV/Pillow, and Vanilla ES6 JavaScript** that allows users to upload chest X-ray images, inspect radiographs side by side with AI-generated report drafts using an interactive zoom slider and hover-to-zoom loupe, ask follow-up questions through a report-grounded chatbot, and manage their persistent analysis history.

---

## Key Features (PRD Version 2.0 Functional Requirements)

- **FR-01 & FR-02 · Secure Registration, Login & Session Protection:**
  - User account creation with email uniqueness validation and Werkzeug password hashing (`scrypt` / `pbkdf2`).
  - Protected routes and strict ownership verification (`user_id`) on all image, report, chat, and deletion operations.
- **FR-03 · Chest X-ray Upload, Validation & Preprocessing:**
  - Supports `.JPG`, `.JPEG`, and `.PNG` chest radiographs up to 16 MB.
  - Verifies image header integrity with Pillow, strips EXIF metadata for privacy, and runs a 512×512 canonical resample + **CLAHE (Contrast Limited Adaptive Histogram Equalization)** pipeline.
  - Includes 4 built-in clinical sample chest radiographs for one-click evaluator testing.
- **FR-04 · Structured AI Report Generation:**
  - Singleton `ThoraxVLMInferenceEngine` loaded once per worker process.
  - Produces structured report drafts with **Findings** (Lungs & Airways, Pleura, Heart & Mediastinum, Bones & Soft Tissues), **Impression / Summary**, **Plain-English Explanation**, **Quantitative Zone Densities**, **Radiological Glossary**, and **Relevant Uncertainty & Limitations**.
  - Explicitly labels all outputs as **AI-Generated & Unverified**.
- **FR-05 · Side-by-Side Analysis Interface:**
  - **Panel A (Left):** Original uploaded chest X-ray preserving aspect ratio inside a dark PACS inspection viewport.
  - **Panel B (Right):** Independently scrollable generated report panel with Structured Clinical View and Raw Report Text tabs.
  - Responsive layout stacks panels cleanly on mobile screens.
- **FR-06 · Interactive X-ray Viewer:**
  - **Zoom Slider (`100%` to `350%`)** with `-`/`+` buttons, live magnification percentage badge, drag-to-pan (mouse and touch), and **Reset (100%)** button.
  - **Desktop Hover-to-Zoom Loupe:** Toggleable optical magnifier lens (`2.0×`, `2.5×`, `3.5×`) that follows the cursor within the viewer boundaries without obscuring the report panel.
  - Switch between **Original Uploaded X-ray**, **CLAHE Contrast-Enhanced View**, and **Invert Grayscale**.
- **FR-07 & FR-08 · English-Only Contextual Chatbot:**
  - Answers follow-up questions grounded strictly in the active chest X-ray report draft (e.g., *"Explain this report in simple English."*, *"What does opacity mean?"*, *"Summarize the report."*, *"What limitations should I understand?"*).
- **FR-09 to FR-12 · Persistent Analysis History Management:**
  - Saves completed analyses and conversations under the authenticated user's account (`Users`, `Analyses`, `ChatMessages`).
  - Reopens saved studies immediately **without triggering a new model inference request**.
  - Ownership-verified deletion with a confirmation dialog that removes the database record, chat messages, and stored image files.

---

## Project Structure

```text
├── app.py                        # Main Flask application, routes, API endpoints & error handlers
├── config.py                     # Environment configuration (MySQL URI builder & SQLite fallback)
├── models.py                     # SQLAlchemy ORM models: Users, Analyses, ChatMessages
├── schema.sql                    # MySQL 8.0+ DDL schema script
├── requirements.txt              # Python dependencies
├── services/
│   ├── image_processor.py        # File validation, EXIF sanitization, CLAHE & zone density metrics
│   ├── ai_report_generator.py    # Singleton ThoraxVLM report generation service
│   ├── chatbot_engine.py         # Report-grounded English-only conversational assistant
│   ├── sample_generator.py       # Synthetic clinical chest radiograph phantom generator
│   └── seed_demo.py              # Demo account & historical study seeder
├── static/
│   ├── css/clinical.css          # Clinical Diagnostic Precision stylesheet
│   ├── js/workspace.js           # Zoom slider, hover-to-zoom loupe, upload & chatbot controller
│   ├── samples/                  # Built-in sample chest radiographs
│   └── uploads/                  # Controlled user upload storage directory
├── templates/
│   ├── base.html                 # Shared header, medical safety banner & delete confirmation modal
│   ├── auth.html                 # Split-screen Registration, Login & One-Click Demo Access
│   ├── dashboard.html            # Side-by-Side Viewer (Panel A), Report (Panel B) & Chatbot
│   └── history.html              # Dedicated Analysis History & Database Schema Dashboard
└── tests/
    └── test_app.py               # Automated pytest suite covering PRD Acceptance Criteria 1–17
```

---

## Setup & Running Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure MySQL Database (Optional — Automatic Local Fallback Included)
To connect to a MySQL 8.0+ server, initialize the schema using `schema.sql` and export your connection variables:
```bash
mysql -u root -p < schema.sql
export MYSQL_HOST="127.0.0.1"
export MYSQL_PORT="3306"
export MYSQL_USER="root"
export MYSQL_PASSWORD="your_password"
export MYSQL_DB="chest_xray_ai_db"
```
*(If `MYSQL_HOST` or `DATABASE_URL` is not set, the application automatically persists to `instance/chest_xray_ai_db.sqlite` via SQLAlchemy ORM using the exact same `Users`, `Analyses`, and `ChatMessages` schema.)*

### 3. Start the Application
```bash
python3 app.py
```

### 4. Run Automated Tests
```bash
pytest -v tests/test_app.py
```
