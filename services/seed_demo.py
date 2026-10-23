"""
Database Initialization & Demo Seeding Module.
Ensures sample radiographs are generated and seeds a rich demo account
(demo@radiology-ai.edu / ClinicalDemo2026!) with 3 historical analyses and
report-grounded chatbot conversations so evaluators can immediately explore
all PRD workflows or register a new account.
"""
import os
import shutil
from datetime import datetime, timedelta, timezone
from models import db, User, Analysis, ChatMessage
from services.sample_generator import ensure_sample_xrays
from services.image_processor import validate_and_preprocess_xray
from services.ai_report_generator import vlm_engine
from services.chatbot_engine import chatbot_engine


SAMPLE_CATALOG = [
    {
        "id": "cxr_normal_pa",
        "filename": "cxr_normal_pa.png",
        "title": "Sample 1: Normal PA Chest Radiograph",
        "subtitle": "Symmetric aerated lungs, sharp costophrenic angles, normal CTR (0.45)",
        "tag": "Normal Reference",
        "hint": "normal_pa",
    },
    {
        "id": "cxr_rll_pneumonia",
        "filename": "cxr_rll_pneumonia.png",
        "title": "Sample 2: Right Lower Zone Consolidation",
        "subtitle": "Focal RLL airspace opacity with internal air bronchograms",
        "tag": "Focal Opacity",
        "hint": "rll_consolidation",
    },
    {
        "id": "cxr_cardiomegaly_effusion",
        "filename": "cxr_cardiomegaly_effusion.png",
        "title": "Sample 3: Cardiomegaly & Basal Pleural Effusion",
        "subtitle": "Enlarged cardiac silhouette (CTR > 0.55) with blunted costophrenic angles",
        "tag": "Cardiac / Pleural",
        "hint": "cardiomegaly_effusion",
    },
    {
        "id": "cxr_lul_infiltrate",
        "filename": "cxr_lul_infiltrate.png",
        "title": "Sample 4: Left Upper Zone Patchy Infiltrate",
        "subtitle": "Localized infraclavicular patchy airspace opacity in left upper lobe",
        "tag": "Upper Zone Opacity",
        "hint": "lul_opacity",
    },
]


def seed_initial_data(app):
    """Creates tables, generates sample CXR images, and seeds demo accounts if not present."""
    with app.app_context():
        db.create_all()
        samples_dir = app.config["SAMPLE_FOLDER"]
        uploads_dir = app.config["UPLOAD_FOLDER"]
        ensure_sample_xrays(samples_dir=samples_dir)

        if not app.config.get("ENABLE_DEMO_ACCESS", True):
            return

        demo_user = User.query.filter_by(email="demo@radiology-ai.edu").first()
        if demo_user is not None:
            return

        # Create primary evaluator demo user
        demo_user = User(
            name="Dr. Elena Vance (Academic Evaluator)",
            email="demo@radiology-ai.edu",
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        demo_user.set_password("ClinicalDemo2026!")
        db.session.add(demo_user)

        # Create secondary student user (demonstrates cross-user record isolation FR-02 / FR-10)
        student_user = User(
            name="Alex Rivera (Biomedical AI Student)",
            email="student@radiology-ai.edu",
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        student_user.set_password("StudentPass2026!")
        db.session.add(student_user)
        db.session.flush()

        # Seed 3 historical analyses for demo_user (ordered oldest to newest so newest appears first)
        seed_cases = [
            {
                "filename": "cxr_normal_pa.png",
                "hint": "normal_pa",
                "time_offset": timedelta(days=2, hours=4),
                "questions": [
                    "Can you explain this report in simple English?",
                    "What does cardiothoracic ratio (CTR) mean?",
                ],
            },
            {
                "filename": "cxr_cardiomegaly_effusion.png",
                "hint": "cardiomegaly_effusion",
                "time_offset": timedelta(days=1, hours=2),
                "questions": [
                    "Can you summarize the findings?",
                    "What does costophrenic angle blunting and pleural effusion mean?",
                    "What limitations should I understand in this report?",
                ],
            },
            {
                "filename": "cxr_rll_pneumonia.png",
                "hint": "rll_consolidation",
                "time_offset": timedelta(hours=3),
                "questions": [
                    "Can you explain this report in simple English?",
                    "What does opacity mean?",
                    "What limitations should I understand in this report?",
                ],
            },
        ]

        now = datetime.now(timezone.utc)
        for item in seed_cases:
            sample_path = os.path.join(samples_dir, item["filename"])
            prep = validate_and_preprocess_xray(sample_path, item["filename"], uploads_dir)
            gen = vlm_engine.generate_report(prep["metrics"], case_hint=item["hint"])
            created_ts = now - item["time_offset"]

            analysis = Analysis(
                user_id=demo_user.user_id,
                image_path=prep["image_rel_path"],
                processed_image_path=prep["processed_rel_path"],
                case_label=gen["case_label"],
                generated_report=gen["report_text"],
                status="completed",
                model_version=gen["model_version"],
                created_at=created_ts,
            )
            analysis.set_metadata(gen["structured_metadata"])
            db.session.add(analysis)
            db.session.flush()

            # Initial assistant welcome message grounded in the report
            welcome_msg = ChatMessage(
                analysis_id=analysis.analysis_id,
                role="assistant",
                message_text=(
                    f"Hello! I have loaded the AI-generated report draft for **{gen['case_label']}**. "
                    "I can explain medical terms (like *opacity*, *consolidation*, or *costophrenic angles*), "
                    "summarize the anatomical findings in plain English, or discuss the model's limitations. "
                    "How can I help you understand this report?"
                ),
                created_at=created_ts + timedelta(seconds=5),
            )
            db.session.add(welcome_msg)

            msg_offset = 25
            for q_text in item["questions"]:
                u_msg = ChatMessage(
                    analysis_id=analysis.analysis_id,
                    role="user",
                    message_text=q_text,
                    created_at=created_ts + timedelta(seconds=msg_offset),
                )
                db.session.add(u_msg)
                ans_text = chatbot_engine.generate_response(q_text, analysis)
                a_msg = ChatMessage(
                    analysis_id=analysis.analysis_id,
                    role="assistant",
                    message_text=ans_text,
                    created_at=created_ts + timedelta(seconds=msg_offset + 4),
                )
                db.session.add(a_msg)
                msg_offset += 30

        # Also seed 1 analysis for student_user to verify cross-user ownership protection
        student_sample = os.path.join(samples_dir, "cxr_lul_infiltrate.png")
        s_prep = validate_and_preprocess_xray(student_sample, "cxr_lul_infiltrate.png", uploads_dir)
        s_gen = vlm_engine.generate_report(s_prep["metrics"], case_hint="lul_opacity")
        s_analysis = Analysis(
            user_id=student_user.user_id,
            image_path=s_prep["image_rel_path"],
            processed_image_path=s_prep["processed_rel_path"],
            case_label=s_gen["case_label"],
            generated_report=s_gen["report_text"],
            status="completed",
            model_version=s_gen["model_version"],
            created_at=now - timedelta(hours=6),
        )
        s_analysis.set_metadata(s_gen["structured_metadata"])
        db.session.add(s_analysis)

        db.session.commit()
