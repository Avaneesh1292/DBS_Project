from flask import Flask, jsonify, request
from flask_cors import CORS

from config import Config
from db import (
    create_category,
    create_challenge,
    create_submission,
    get_team_progress,
    get_leaderboard,
    list_admin_submissions,
    list_categories,
    list_challenges,
    list_hints,
    login_student,
    ping_database,
    register_student,
    unlock_hint,
)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": Config.cors_origins()}})


def _parse_int(value, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer")


@app.get("/api/health")
def health() -> tuple:
    return jsonify({"status": "up", "service": "ctf-backend"}), 200


@app.get("/api/db/ping")
def db_ping() -> tuple:
    try:
        result = ping_database()
        return jsonify({"ok": True, "message": "Database connected", "data": result}), 200
    except Exception as ex:
        return jsonify({"ok": False, "message": "Database connection failed", "error": str(ex)}), 500


@app.post("/api/auth/register")
def auth_register() -> tuple:
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    team_name = (payload.get("team_name") or "").strip()

    if not name or not email or not team_name:
        return jsonify({"message": "name, email and team_name are required"}), 400

    try:
        data = register_student(name=name, email=email, team_name=team_name)
        return jsonify(data), 201
    except ValueError as ex:
        return jsonify({"message": str(ex)}), 400
    except Exception as ex:
        return jsonify({"message": "Registration failed", "error": str(ex)}), 500


@app.post("/api/auth/login")
def auth_login() -> tuple:
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()
    if not email:
        return jsonify({"message": "email is required"}), 400

    try:
        data = login_student(email=email)
        return jsonify(data), 200
    except ValueError as ex:
        return jsonify({"message": str(ex)}), 404
    except Exception as ex:
        return jsonify({"message": "Login failed", "error": str(ex)}), 500


@app.get("/api/categories")
def categories() -> tuple:
    try:
        data = list_categories()
        return jsonify({"categories": data}), 200
    except Exception as ex:
        return jsonify({"message": "Failed to fetch categories", "error": str(ex)}), 500


@app.get("/api/challenges")
def challenges() -> tuple:
    try:
        category_id = _parse_int(request.args.get("category_id"), "category_id")
        team_id = _parse_int(request.args.get("team_id"), "team_id")
        data = list_challenges(category_id=category_id, team_id=team_id)
        return jsonify({"challenges": data}), 200
    except ValueError as ex:
        return jsonify({"message": str(ex)}), 400
    except Exception as ex:
        return jsonify({"message": "Failed to fetch challenges", "error": str(ex)}), 500


@app.get("/api/teams/<int:team_id>/progress")
def team_progress(team_id: int) -> tuple:
    try:
        data = get_team_progress(team_id=team_id)
        return jsonify(data), 200
    except ValueError as ex:
        return jsonify({"message": str(ex)}), 404
    except Exception as ex:
        return jsonify({"message": "Failed to fetch team progress", "error": str(ex)}), 500


@app.get("/api/challenges/<int:challenge_no>/hints")
def challenge_hints(challenge_no: int) -> tuple:
    try:
        data = list_hints(challenge_no=challenge_no)
        return jsonify({"hints": data}), 200
    except Exception as ex:
        return jsonify({"message": "Failed to fetch hints", "error": str(ex)}), 500


@app.post("/api/hints/unlock")
def hints_unlock() -> tuple:
    payload = request.get_json(silent=True) or {}
    team_id = payload.get("team_id")
    hint_id = payload.get("hint_id")
    if team_id is None or hint_id is None:
        return jsonify({"message": "team_id and hint_id are required"}), 400

    try:
        result = unlock_hint(team_id=int(team_id), hint_id=int(hint_id))
        return jsonify(result), 200
    except ValueError as ex:
        return jsonify({"message": str(ex)}), 400
    except Exception as ex:
        return jsonify({"message": "Failed to unlock hint", "error": str(ex)}), 500


@app.post("/api/submissions")
def submissions() -> tuple:
    payload = request.get_json(silent=True) or {}
    required = ["team_id", "student_id", "challenge_no", "submitted_answer"]
    if any(payload.get(key) in [None, ""] for key in required):
        return jsonify({"message": "team_id, student_id, challenge_no and submitted_answer are required"}), 400

    try:
        result = create_submission(
            team_id=int(payload["team_id"]),
            student_id=int(payload["student_id"]),
            challenge_no=int(payload["challenge_no"]),
            submitted_answer=str(payload["submitted_answer"]),
        )
        return jsonify(result), 201
    except ValueError as ex:
        return jsonify({"message": str(ex)}), 400
    except Exception as ex:
        return jsonify({"message": "Failed to submit flag", "error": str(ex)}), 500


@app.get("/api/leaderboard")
def leaderboard() -> tuple:
    try:
        data = get_leaderboard()
        return jsonify({"leaderboard": data}), 200
    except Exception as ex:
        return jsonify({"message": "Failed to fetch leaderboard", "error": str(ex)}), 500


@app.post("/api/admin/categories")
def admin_categories_create() -> tuple:
    payload = request.get_json(silent=True) or {}
    category_name = (payload.get("category_name") or "").strip()
    description = (payload.get("description") or "").strip()
    if not category_name:
        return jsonify({"message": "category_name is required"}), 400

    try:
        result = create_category(category_name=category_name, description=description)
        return jsonify(result), 201
    except Exception as ex:
        return jsonify({"message": "Failed to create category", "error": str(ex)}), 500


@app.post("/api/admin/challenges")
def admin_challenges_create() -> tuple:
    payload = request.get_json(silent=True) or {}
    required = ["category_id", "question_text", "answer", "points"]
    if any(payload.get(key) in [None, ""] for key in required):
        return jsonify({"message": "category_id, question_text, answer and points are required"}), 400

    try:
        result = create_challenge(
            category_id=int(payload["category_id"]),
            question_text=str(payload["question_text"]),
            answer=str(payload["answer"]),
            points=int(payload["points"]),
        )
        return jsonify(result), 201
    except Exception as ex:
        return jsonify({"message": "Failed to create challenge", "error": str(ex)}), 500


@app.get("/api/admin/submissions")
def admin_submissions_list() -> tuple:
    try:
        data = list_admin_submissions()
        return jsonify({"submissions": data}), 200
    except Exception as ex:
        return jsonify({"message": "Failed to fetch submissions", "error": str(ex)}), 500


if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=(Config.FLASK_ENV == "development"))
