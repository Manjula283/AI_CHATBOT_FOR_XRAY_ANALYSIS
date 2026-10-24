# ThoraxAI — Chest X-ray Analysis Chatbot

ThoraxAI is a web-based chest X-ray analysis application that combines image processing, quantitative analysis, structured report generation, and conversational interaction in a unified workspace.

The objective of this project is to demonstrate an integrated workflow for uploading chest X-ray images, processing image data, evaluating quantitative indicators, generating educational analysis reports, and allowing users to explore the results through an interactive chatbot.

## Features

### 1. Chest X-ray Image Upload
- Upload chest X-ray images in JPG, JPEG, and PNG formats.
- Validate uploaded files and their sizes.
- Preprocess images before analysis.
- Remove EXIF metadata to help protect image privacy.
- Apply image normalization and contrast enhancement.

### 2. Image Preprocessing
- Convert images to grayscale for analysis.
- Normalize image intensity values.
- Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to enhance local contrast.
- Prepare images for quantitative measurements and visualization.

### 3. Quantitative Image Analysis
The application evaluates image-based indicators, including:

- **Cardiothoracic Ratio (CTR):** Estimates the ratio between cardiac width and thoracic width.
- **Lung-Zone Density:** Examines density variations across defined lung regions.
- **Lung Symmetry Index:** Compares measurements between the left and right lung regions.
- **Costophrenic-Angle Density:** Evaluates image density near the costophrenic regions.

These indicators are evaluated by the application's rule-based inference engine to generate an educational analysis.

### 4. Interactive X-ray Viewer
- Zoom in and out of uploaded images.
- Pan across images for closer inspection.
- Use hover-based zoom for focused viewing.
- Apply contrast enhancement.
- Invert image intensity for alternative visualization.

### 5. Automated Report Generation
The application generates structured reports containing:

- Analysis summary and impression.
- Region-wise image observations.
- Quantitative measurements.
- Plain-English explanations.
- Consolidated analysis results.

### 6. Chatbot Interface
The integrated chatbot allows users to ask questions about the generated analysis and receive contextual explanations based on the application's analysis results.

### 7. User Authentication
- User registration and login.
- User-specific analysis access.
- Database-backed user management.

### 8. Analysis History
- Save analysis records in the database.
- Retrieve previous analyses.
- Review previously generated reports.
- Associate analysis records with individual users.

## How It Works

1. **Upload:** The user uploads a chest X-ray image.
2. **Validation:** The application validates the file format and size.
3. **Preprocessing:** The image is normalized, enhanced, and prepared for analysis.
4. **Quantitative Analysis:** The application calculates image-based indicators such as CTR, lung-zone density, and symmetry measurements.
5. **Rule-Based Inference:** The inference engine evaluates computed measurements and image characteristics using predefined rules.
6. **Report Generation:** The application generates a structured report containing observations and explanations.
7. **Chatbot Interaction:** The user can ask questions about the generated report.
8. **History Management:** The analysis and report can be saved and retrieved for later review.

## Technology Stack

| Component | Technologies |
|---|---|
| Programming Language | Python |
| Backend Framework | Flask |
| Frontend | HTML5, CSS3, JavaScript (ES6) |
| Image Processing | OpenCV, Pillow, NumPy |
| Database ORM | Flask-SQLAlchemy, SQLAlchemy |
| Database | MySQL 8.0+ / SQLite fallback |
| Database Connectivity | PyMySQL |
| Testing | pytest |
| Deployment | Render |
| Cloud Database | PostgreSQL-compatible configuration |

## Project Architecture

The application follows a modular architecture that separates the web application, image processing, inference logic, report generation, chatbot functionality, and database operations.

```text
ThoraxAI/
│
├── app.py
├── config.py
├── models.py
├── schema.sql
├── requirements.txt
├── render.yaml
│
├── services/
│   ├── image_processor.py
│   ├── ai_report_generator.py
│   ├── chatbot_engine.py
│   ├── sample_generator.py
│   └── seed_demo.py
│
├── templates/
│   ├── base.html
│   ├── auth.html
│   ├── dashboard.html
│   ├── upload.html
│   ├── report.html
│   └── history.html
│
├── static/
│   ├── css/
│   │   └── clinical.css
│   ├── js/
│   │   └── workspace.js
│   ├── samples/
│   └── uploads/
│
├── tests/
│   ├── test_app.py
│   └── test_database_migrations.py
│
├── DEPLOY.md
├── DEPLOY_GUIDE.md
└── README.md
```

*Note: Verify the file names and directory structure against the actual repository.*

## Database Design

The application uses a relational database to manage user accounts, analysis records, and chatbot conversations.

### USERS
Stores user account information.

### ANALYSES
Stores analysis metadata, quantitative measurements, and generated reports. Each analysis is associated with a user.

### CHAT_MESSAGES
Stores chatbot messages associated with an analysis.

**Database relationships:**
- One user can have multiple analysis records.
- One analysis can have multiple chatbot messages.
- Each analysis record stores its generated report.

## Installation and Setup

### Prerequisites
- Python 3.10 or later
- pip
- Git
- MySQL 8.0+ or SQLite for local development

### 1. Clone the Repository

```bash
git clone https://github.com/Manjula283/AI_CHATBOT_FOR_XRAY_ANALYSIS.git
cd AI_CHATBOT_FOR_XRAY_ANALYSIS
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate the environment on Windows:

```bash
venv\Scripts\activate
```

On macOS or Linux:

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Configure the database connection and application settings using the environment variables supported by the project.

Example:

```env
SECRET_KEY=your-secret-key
DATABASE_URL=your-database-connection-string
```

Use a secure secret key and keep credentials in environment variables rather than committing them to GitHub.

### 5. Run the Application

```bash
python app.py
```

Open the local address displayed by Flask in your browser, commonly `http://127.0.0.1:5000`.

*Database initialization and environment variable names should follow the actual application configuration.*

## Testing

Run the automated test suite using:

```bash
pytest
```

The test suite can be used to verify application routes, core functionality, and database-related behavior.

## Deployment

The project includes deployment configuration and documentation intended for hosting the Flask application on Render.

Typical deployment steps:

1. Push the project to GitHub.
2. Connect the repository to Render.
3. Configure the required environment variables.
4. Configure a supported production database.
5. Deploy the application.
6. Verify authentication, image upload, report generation, chatbot interactions, and analysis history.

**Hosted application:** [ThoraxAI — Chest X-ray Analysis Chatbot](https://thoraxai-chest-xray.onrender.com)

## Current Implementation

ThoraxAI currently demonstrates image-based analysis through a custom rule-based inference engine. It evaluates computed image measurements and predefined conditions to produce structured educational reports. The application separates image processing, inference, report generation, and chatbot logic into modular components.

## Project Contributors

This project was developed collaboratively by:

- **Manjula**
- **Eshwari**

## Project Repository

[AI Chatbot for X-ray Analysis — GitHub](https://github.com/Manjula283/AI_CHATBOT_FOR_XRAY_ANALYSIS)

## Acknowledgments

We acknowledge the guidance and support provided during the development of this project.

---

*ThoraxAI — Combining image processing, quantitative analysis, and conversational interaction in one workspace.*
