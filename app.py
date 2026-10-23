"""
Main Flask Application — AI Chest X-ray Analysis Chatbot with Login,
Interactive Image Viewer, and Analysis History (PRD Version 2.0).
Includes Dual-Mode Session Management so authentication works seamlessly both
in standalone browsers and inside cross-origin preview iframes that block cookies.
"""
import os
import re
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    send_from_directory,
    send_file,
    abort,
)
from io import BytesIO
from sqlalchemy import text
from werkzeug.exceptions import RequestEntityTooLarge
from config import Config
from models import db, User, Analysis, ChatMessage
from services.image_processor import validate_and_preprocess_xray, ImageValidationError
from services.ai_report_generator import vlm_engine
from services.chatbot_engine import chatbot_engine
from services.seed_demo import seed_initial_data, SAMPLE_CATALOG


def create_app(test_config: dict = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    if app.config.get("APP_ENV") == "production" and not app.config.get("SECRET_KEY"):
        raise RuntimeError("FLASK_SECRET_KEY must be configured in production.")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["SAMPLE_FOLDER"], exist_ok=True)

    db.init_app(app)

    if not app.config.get("TESTING", False):
        seed_initial_data(app)

    # -------------------------------------------------------------------------
    # Dual-Mode Session Persistence (Cookie + Iframe Fallback)
    # -------------------------------------------------------------------------
    def _set_active_user(user_obj: User) -> None:
        session.clear()
        session["user_id"] = user_obj.user_id
        session["user_name"] = user_obj.name

    def _clear_active_user() -> None:
        session.clear()

    def get_current_user():
        uid = session.get("user_id")
        if uid:
            user = db.session.get(User, uid)
            if user:
                return user

        return None

    def _seed_starter_study_for_new_user(user_obj: User) -> None:
        """Gives a newly registered interactive user 1 starter chest X-ray analysis so their workspace is immediately populated."""
        if app.config.get("TESTING", False):
            return
        existing_count = Analysis.query.filter_by(user_id=user_obj.user_id).count()
        if existing_count > 0:
            return
        try:
            sample_path = os.path.join(app.config["SAMPLE_FOLDER"], "cxr_rll_pneumonia.png")
            if not os.path.exists(sample_path):
                return
            prep = validate_and_preprocess_xray(sample_path, "cxr_rll_pneumonia.png", app.config["UPLOAD_FOLDER"])
            gen = vlm_engine.generate_report(prep["metrics"], case_hint="rll_consolidation")
            starter = Analysis(
                user_id=user_obj.user_id,
                image_path=prep["image_rel_path"],
                processed_image_path=prep["processed_rel_path"],
                original_image_bytes=prep["orig_bytes"],
                processed_image_bytes=prep["proc_bytes"],
                case_label=gen["case_label"],
                generated_report=gen["report_text"],
                status="completed",
                model_version=gen["model_version"],
            )
            starter.set_metadata(gen["structured_metadata"])
            db.session.add(starter)
            db.session.flush()
            greeting = ChatMessage(
                analysis_id=starter.analysis_id,
                role="assistant",
                message_text=(
                    f"Welcome, **{user_obj.name}**! I have loaded a starter chest X-ray analysis (**{gen['case_label']}**) "
                    "so you can immediately test the **Side-by-Side Image Viewer**, **Zoom Slider**, **Hover-to-Zoom Loupe**, "
                    "and **Contextual Chatbot**, or click **Upload X-ray** at the top to upload your own image!"
                ),
            )
            db.session.add(greeting)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def login_required(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            user = get_current_user()
            if user is None:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required. Please log in."}), 401
                flash("Please log in to access the clinical analysis workspace.", "warning")
                return redirect(url_for("login"))
            return view_func(*args, **kwargs)

        return wrapped_view

    @app.context_processor
    def inject_globals():
        user = get_current_user()
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        db_engine_label = "MySQL 8.0 (SQLAlchemy ORM)" if "mysql" in db_uri else "MySQL-Compatible SQLAlchemy ORM (Local Instance)"
        return {
            "current_user": user,
            "vlm_model_name": app.config.get("DEFAULT_VLM_VERSION"),
            "chat_model_name": app.config.get("DEFAULT_CHAT_MODEL"),
            "db_engine_label": db_engine_label,
            "sample_catalog": SAMPLE_CATALOG,
        }

    # -------------------------------------------------------------------------
    # Error Handlers (FR-13: Error Handling)
    # -------------------------------------------------------------------------
    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "File size exceeds the 16 MB maximum limit. Please upload a smaller JPG or PNG image."}), 413
        flash("Uploaded file exceeds the 16 MB size limit. Please upload a smaller chest X-ray image.", "danger")
        return redirect(url_for("dashboard"))

    @app.errorhandler(403)
    def handle_forbidden(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Access denied: You do not have permission to access another user's analysis record."}), 403
        flash("Access denied: You can only view or modify your own chest X-ray analyses.", "danger")
        return redirect(url_for("dashboard")), 403

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "The requested analysis record or resource could not be found."}), 404
        # Browsers and crawlers probe for asset paths (e.g. /favicon.ico);
        # a missing asset must not flash a warning banner on the page.
        if request.path.startswith("/static") or request.accept_mimetypes.best != "text/html":
            return "Not found", 404
        flash("The requested page or analysis record could not be found.", "warning")
        return redirect(url_for("dashboard") if get_current_user() else url_for("login")), 404

    @app.errorhandler(500)
    def handle_internal_error(e):
        db.session.rollback()
        if request.path.startswith("/api/"):
            return jsonify({"error": "An unexpected internal error occurred. No incomplete report was saved."}), 500
        flash("An unexpected error occurred while processing your request. Please try again.", "danger")
        return redirect(url_for("dashboard") if get_current_user() else url_for("login")), 500

    # -------------------------------------------------------------------------
    # Public & Authentication Routes (FR-01, FR-02)
    # -------------------------------------------------------------------------
    @app.route("/healthz")
    def health_check():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"status": "ok"})
        except Exception:
            db.session.rollback()
            return jsonify({"status": "unavailable"}), 503

    @app.route("/")
    def index():
        if get_current_user():
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "GET" and get_current_user():
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            confirm_password = request.form.get("confirm_password") or ""

            if not name or not email or not password:
                flash("All fields (Name, Email Address, and Password) are required.", "danger")
                return render_template("auth.html", mode="register", form_name=name, form_email=email), 400

            if len(name) < 2 or len(name) > 120:
                flash("Name must be between 2 and 120 characters.", "danger")
                return render_template("auth.html", mode="register", form_name=name, form_email=email), 400

            email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            if not re.match(email_regex, email):
                flash("Please enter a valid email address.", "danger")
                return render_template("auth.html", mode="register", form_name=name, form_email=email), 400

            if len(password) < 6:
                flash("Password must be at least 6 characters long for account security.", "danger")
                return render_template("auth.html", mode="register", form_name=name, form_email=email), 400

            if confirm_password and password != confirm_password:
                flash("Passwords do not match. Please verify your password confirmation.", "danger")
                return render_template("auth.html", mode="register", form_name=name, form_email=email), 400

            existing = User.query.filter_by(email=email).first()
            if existing:
                flash("An account with this email address already exists. Please log in or use a different email.", "danger")
                return render_template("auth.html", mode="register", form_name=name, form_email=email), 409

            try:
                new_user = User(name=name, email=email)
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()

                _seed_starter_study_for_new_user(new_user)
                _set_active_user(new_user)
                flash(f"Welcome, {new_user.name}! Your account has been created.", "success")
                return redirect(url_for("dashboard"))
            except Exception:
                db.session.rollback()
                flash("Database error occurred during registration. Please try again.", "danger")
                return render_template("auth.html", mode="register", form_name=name, form_email=email), 500

        return render_template("auth.html", mode="register")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET" and get_current_user():
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""

            if not email or not password:
                flash("Please enter both your email address and password.", "danger")
                return render_template("auth.html", mode="login", form_email=email), 400

            user = User.query.filter_by(email=email).first()

            if user is None or not user.check_password(password):
                flash("Invalid email address or password. Please check your credentials and try again.", "danger")
                return render_template("auth.html", mode="login", form_email=email), 401

            _set_active_user(user)
            flash(f"Signed in as {user.name}.", "success")
            return redirect(url_for("dashboard"))

        return render_template("auth.html", mode="login")

    @app.route("/demo-login", methods=["POST", "GET"])
    def demo_login():
        """One-click evaluator login into the pre-seeded demo account."""
        if not app.config.get("ENABLE_DEMO_ACCESS"):
            abort(404)
        role = request.values.get("demo_role", "evaluator")
        target_email = "student@radiology-ai.edu" if role == "student" else "demo@radiology-ai.edu"
        user = User.query.filter_by(email=target_email).first()
        if not user:
            seed_initial_data(app)
            user = User.query.filter_by(email=target_email).first()
        if user is None:
            abort(404)
        _set_active_user(user)
        flash(f"Signed in with Demo Account: {user.name}", "info")
        return redirect(url_for("dashboard"))

    @app.route("/logout", methods=["POST", "GET"])
    def logout():
        _clear_active_user()
        flash("You have been securely logged out.", "info")
        return redirect(url_for("login"))

    # -------------------------------------------------------------------------
    # Main Workspace & History Dashboard Routes (FR-05, FR-10, FR-11)
    # -------------------------------------------------------------------------
    @app.route("/dashboard")
    @login_required
    def dashboard():
        user = get_current_user()
        analyses = (
            Analysis.query.filter_by(user_id=user.user_id)
            .order_by(Analysis.created_at.desc(), Analysis.analysis_id.desc())
            .all()
        )

        requested_id = request.args.get("analysis_id", type=int)
        new_mode = request.args.get("new", type=int) == 1
        active_analysis = None

        if requested_id is not None:
            candidate = db.session.get(Analysis, requested_id)
            if candidate is None:
                flash("The requested analysis record does not exist.", "warning")
                return redirect(url_for("dashboard"))
            if candidate.user_id != user.user_id:
                abort(403)
            active_analysis = candidate
        elif analyses:
            active_analysis = analyses[0]

        return render_template(
            "dashboard.html",
            analyses=analyses,
            active_analysis=active_analysis,
            active_dict=active_analysis.to_dict(include_messages=True) if active_analysis else None,
            new_mode=new_mode or (active_analysis is None),
        )

    @app.route("/analysis/<int:analysis_id>")
    @login_required
    def view_analysis(analysis_id: int):
        user = get_current_user()
        analysis = db.session.get(Analysis, analysis_id)
        if analysis is None:
            abort(404)
        if analysis.user_id != user.user_id:
            abort(403)

        analyses = (
            Analysis.query.filter_by(user_id=user.user_id)
            .order_by(Analysis.created_at.desc(), Analysis.analysis_id.desc())
            .all()
        )
        return render_template(
            "dashboard.html",
            analyses=analyses,
            active_analysis=analysis,
            active_dict=analysis.to_dict(include_messages=True),
            new_mode=False,
        )

    @app.route("/history")
    @login_required
    def history_page():
        user = get_current_user()
        analyses = (
            Analysis.query.filter_by(user_id=user.user_id)
            .order_by(Analysis.created_at.desc(), Analysis.analysis_id.desc())
            .all()
        )
        return render_template(
            "history.html",
            analyses=analyses,
            analyses_dicts=[a.to_dict(include_messages=True) for a in analyses],
        )

    # -------------------------------------------------------------------------
    # Ownership-Protected Image Delivery Routes (Section 10 Security)
    # -------------------------------------------------------------------------
    @app.route("/analysis/<int:analysis_id>/image")
    @login_required
    def serve_analysis_image(analysis_id: int):
        user = get_current_user()
        analysis = db.session.get(Analysis, analysis_id)
        if analysis is None:
            abort(404)
        if analysis.user_id != user.user_id:
            abort(403)

        # Cloud-first: serve the image bytes stored in the database.
        # Built-in samples (and any legacy local rows) fall back to the file.
        if analysis.original_image_bytes:
            mimetype = "image/png" if (analysis.image_path or "").lower().endswith(".png") else "image/jpeg"
            return send_file(
                BytesIO(analysis.original_image_bytes),
                mimetype=mimetype,
                download_name=os.path.basename(analysis.image_path),
            )
        rel_path = analysis.image_path
        static_root = os.path.join(app.root_path, "static")
        full_path = os.path.join(static_root, rel_path)
        if not os.path.exists(full_path):
            abort(404)
        directory, filename = os.path.split(full_path)
        return send_from_directory(directory, filename)

    @app.route("/analysis/<int:analysis_id>/processed-image")
    @login_required
    def serve_processed_image(analysis_id: int):
        user = get_current_user()
        analysis = db.session.get(Analysis, analysis_id)
        if analysis is None:
            abort(404)
        if analysis.user_id != user.user_id:
            abort(403)

        # Cloud-first: serve the stored CLAHE bytes (original bytes as fallback).
        proc_blob = analysis.processed_image_bytes or analysis.original_image_bytes
        if proc_blob:
            return send_file(
                BytesIO(proc_blob),
                mimetype="image/png",
                download_name=os.path.basename(analysis.processed_image_path or analysis.image_path),
            )
        rel_path = analysis.processed_image_path or analysis.image_path
        static_root = os.path.join(app.root_path, "static")
        full_path = os.path.join(static_root, rel_path)
        if not os.path.exists(full_path):
            abort(404)
        directory, filename = os.path.split(full_path)
        return send_from_directory(directory, filename)

    # -------------------------------------------------------------------------
    # Upload & AI Report Generation Endpoint (FR-03, FR-04, FR-09, FR-13)
    # -------------------------------------------------------------------------
    @app.route("/api/analyze", methods=["POST"])
    @login_required
    def api_analyze_xray():
        user = get_current_user()
        sample_id = (request.form.get("sample_id") or "").strip()
        uploaded_file = request.files.get("xray_image")

        try:
            if sample_id:
                sample_entry = next((s for s in SAMPLE_CATALOG if s["id"] == sample_id), None)
                if not sample_entry:
                    return jsonify({"error": "Selected sample radiograph was not found."}), 400
                sample_path = os.path.join(app.config["SAMPLE_FOLDER"], sample_entry["filename"])
                prep = validate_and_preprocess_xray(
                    sample_path,
                    sample_entry["filename"],
                    app.config["UPLOAD_FOLDER"],
                )
                case_hint = sample_entry["hint"]
            else:
                if uploaded_file is None or uploaded_file.filename == "":
                    return jsonify({
                        "error": "No image file selected. Please choose a JPG, JPEG, or PNG chest X-ray image to upload."
                    }), 400

                prep = validate_and_preprocess_xray(
                    uploaded_file.stream,
                    uploaded_file.filename,
                    app.config["UPLOAD_FOLDER"],
                )
                case_hint = request.form.get("case_hint", "")

        except ImageValidationError as val_err:
            return jsonify({"error": str(val_err)}), 400
        except Exception:
            return jsonify({"error": "Failed to validate and preprocess the uploaded image."}), 400

        if request.form.get("simulate_inference_error") == "1":
            return jsonify({
                "error": "Model inference failed or timed out. No partial report was saved. Please retry your upload."
            }), 502

        try:
            gen_result = vlm_engine.generate_report(prep["metrics"], case_hint=case_hint)

            new_analysis = Analysis(
                user_id=user.user_id,
                image_path=prep["image_rel_path"],
                processed_image_path=prep["processed_rel_path"],
                original_image_bytes=prep["orig_bytes"],
                processed_image_bytes=prep["proc_bytes"],
                case_label=gen_result["case_label"],
                generated_report=gen_result["report_text"],
                status="completed",
                model_version=gen_result["model_version"],
            )
            new_analysis.set_metadata(gen_result["structured_metadata"])
            db.session.add(new_analysis)
            db.session.flush()

            greeting = ChatMessage(
                analysis_id=new_analysis.analysis_id,
                role="assistant",
                message_text=(
                    f"Your report for **{gen_result['case_label']}** is ready. "
                    "You can inspect the X-ray on the left using the **Zoom Slider** or **Hover-to-Zoom Loupe**, "
                    "read the structured findings on the right, and ask me any follow-up questions below!"
                ),
            )
            db.session.add(greeting)
            db.session.commit()

            return jsonify({
                "status": "completed",
                "message": "Chest X-ray analyzed and saved to your history.",
                "redirect_url": url_for("view_analysis", analysis_id=new_analysis.analysis_id),
                "analysis": new_analysis.to_dict(include_messages=True),
            }), 201

        except Exception:
            db.session.rollback()
            return jsonify({
                "error": "An error occurred during AI report generation or database persistence. No incomplete analysis was saved."
            }), 500

    # -------------------------------------------------------------------------
    # Contextual Report-Grounded Chatbot Endpoint (FR-07)
    # -------------------------------------------------------------------------
    @app.route("/api/analysis/<int:analysis_id>/chat", methods=["POST"])
    @login_required
    def api_chat(analysis_id: int):
        user = get_current_user()
        analysis = db.session.get(Analysis, analysis_id)
        if analysis is None:
            return jsonify({"error": "Analysis record not found."}), 404
        if analysis.user_id != user.user_id:
            return jsonify({"error": "Access denied: You cannot access another user's analysis."}), 403

        payload = request.get_json(silent=True) or {}
        question = (payload.get("message") or request.form.get("message") or "").strip()
        if not question:
            return jsonify({"error": "Please enter a question about the chest X-ray report."}), 400
        if len(question) > 1000:
            return jsonify({"error": "Question is too long (maximum 1,000 characters)."}), 400

        try:
            user_msg = ChatMessage(
                analysis_id=analysis.analysis_id,
                role="user",
                message_text=question,
            )
            db.session.add(user_msg)
            db.session.flush()

            reply_text = chatbot_engine.generate_response(
                question,
                analysis,
                chat_history=analysis.messages,
            )

            assistant_msg = ChatMessage(
                analysis_id=analysis.analysis_id,
                role="assistant",
                message_text=reply_text,
            )
            db.session.add(assistant_msg)
            db.session.commit()

            return jsonify({
                "status": "ok",
                "user_message": user_msg.to_dict(),
                "assistant_message": assistant_msg.to_dict(),
            })
        except Exception:
            db.session.rollback()
            return jsonify({"error": "Failed to process chatbot message. Please try again."}), 500

    # -------------------------------------------------------------------------
    # Reopen / Fetch Saved Analysis JSON Endpoint (FR-11)
    # -------------------------------------------------------------------------
    @app.route("/api/analysis/<int:analysis_id>", methods=["GET"])
    @login_required
    def api_get_analysis(analysis_id: int):
        user = get_current_user()
        analysis = db.session.get(Analysis, analysis_id)
        if analysis is None:
            return jsonify({"error": "Analysis record not found."}), 404
        if analysis.user_id != user.user_id:
            return jsonify({"error": "Access denied: Record belongs to another user."}), 403

        return jsonify({
            "status": "ok",
            "inference_triggered": False,
            "analysis": analysis.to_dict(include_messages=True),
        })

    # -------------------------------------------------------------------------
    # Delete Saved Analysis Endpoint (FR-12)
    # -------------------------------------------------------------------------
    @app.route("/api/analysis/<int:analysis_id>/delete", methods=["POST", "DELETE"])
    @login_required
    def api_delete_analysis(analysis_id: int):
        user = get_current_user()
        analysis = db.session.get(Analysis, analysis_id)
        if analysis is None:
            return jsonify({"error": "Analysis record not found."}), 404
        if analysis.user_id != user.user_id:
            return jsonify({"error": "Access denied: You can only delete your own analysis records."}), 403

        static_root = os.path.join(app.root_path, "static")
        paths_to_remove = []
        for rel in [analysis.image_path, analysis.processed_image_path]:
            if rel and rel.startswith("uploads/"):
                abs_p = os.path.join(static_root, rel)
                paths_to_remove.append(abs_p)

        try:
            db.session.delete(analysis)
            db.session.commit()

            for file_p in set(paths_to_remove):
                if os.path.exists(file_p):
                    try:
                        os.remove(file_p)
                    except OSError:
                        pass

            if request.accept_mimetypes.best == "application/json" or request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "status": "deleted",
                    "deleted_analysis_id": analysis_id,
                    "message": f"Analysis #{analysis_id} and its associated conversation and images have been permanently deleted.",
                })

            flash(f"Analysis record #{analysis_id} was deleted.", "info")
            return redirect(url_for("dashboard"))
        except Exception:
            db.session.rollback()
            return jsonify({"error": "Database error while attempting to delete the analysis record."}), 500

    # -------------------------------------------------------------------------
    # Database Schema & User Record Inspector API
    # -------------------------------------------------------------------------
    @app.route("/api/schema-status")
    @login_required
    def api_schema_status():
        user = get_current_user()
        user_analyses = Analysis.query.filter_by(user_id=user.user_id).all()
        analysis_ids = [a.analysis_id for a in user_analyses]
        msg_count = ChatMessage.query.filter(ChatMessage.analysis_id.in_(analysis_ids)).count() if analysis_ids else 0
        return jsonify({
            "tables": ["Users", "Analyses", "ChatMessages"],
            "authenticated_user": user.to_dict(),
            "user_analyses_count": len(user_analyses),
            "user_chat_messages_count": msg_count,
            "english_only_enforced": True,
        })

    @app.route("/download-project-zip")
    def download_project_zip():
        """Direct browser download endpoint for the complete project ZIP archive."""
        zip_dir = app.root_path
        zip_filename = "Chest_Xray_AI_Chatbot_Project.zip"
        full_zip_path = os.path.join(zip_dir, zip_filename)
        if not os.path.exists(full_zip_path):
            abort(404)
        return send_from_directory(
            zip_dir,
            zip_filename,
            as_attachment=True,
            download_name="Chest_Xray_AI_Chatbot_Project.zip",
        )

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
