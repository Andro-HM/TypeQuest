import json
import math
import sqlite3
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from database import (
    create_profile,
    get_active_profile,
    get_classic_summary,
    initialize_database,
    list_classic_progress,
    list_profiles,
    list_recent_classic_sessions,
    save_classic_result,
    select_profile,
)
from progression import find_classic_block, get_classic_block_statuses


app = Flask(__name__)
DATABASE_PATH = Path(app.instance_path) / "typequest.sqlite3"
CLASSIC_CONTENT_PATH = Path(app.root_path) / "content" / "classic.json"
initialize_database(DATABASE_PATH)


def load_classic_levels():
    with CLASSIC_CONTENT_PATH.open(encoding="ascii") as content_file:
        content = json.load(content_file)
    return content["levels"]


def find_classic_level(level_id):
    for level in load_classic_levels():
        if level["id"] == level_id:
            return level
    return None


def recompute_classic_result(typed_buffer, target, active_elapsed_ms):
    correct_positions = 0
    for index in range(len(target)):
        if typed_buffer[index] == target[index]:
            correct_positions += 1

    retained_characters = len(typed_buffer)
    opportunity_positions = len(typed_buffer)
    active_elapsed_minutes = active_elapsed_ms / 60000
    raw_wpm = (
        retained_characters / 5 / active_elapsed_minutes
        if active_elapsed_minutes > 0 else 0
    )
    accuracy = (
        correct_positions / opportunity_positions
        if opportunity_positions > 0 else 0
    )
    net_wpm = raw_wpm * accuracy

    if accuracy >= 0.95:
        stars_earned = 3
    elif accuracy >= 0.90:
        stars_earned = 2
    else:
        stars_earned = 1

    return {
        "active_elapsed_ms": active_elapsed_ms,
        "retained_characters": retained_characters,
        "correct_positions": correct_positions,
        "opportunity_positions": opportunity_positions,
        "raw_wpm": raw_wpm,
        "accuracy": accuracy,
        "net_wpm": net_wpm,
        "stars_earned": stars_earned,
    }


def profile_page(error=None, entered_name=""):
    return render_template(
        "profiles.html",
        profiles=list_profiles(DATABASE_PATH),
        active_profile=get_active_profile(DATABASE_PATH),
        error=error,
        entered_name=entered_name,
    )


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/play")
def play():
    return render_template("play.html")


@app.route("/play/classic")
def classic_levels():
    active_profile = get_active_profile(DATABASE_PATH)
    saved_progress = []
    if active_profile is not None:
        saved_progress = list_classic_progress(DATABASE_PATH, active_profile["id"])
    progress_by_level = {row["level_id"]: row for row in saved_progress}
    blocks = get_classic_block_statuses(saved_progress)
    levels = load_classic_levels()
    for block in blocks:
        block["levels"] = [
            level for level in levels
            if block["first_level"] <= level["id"] <= block["last_level"]
        ]
    return render_template(
        "classic_levels.html",
        blocks=blocks,
        active_profile=active_profile,
        progress_by_level=progress_by_level,
    )


@app.route("/play/classic/<int:level_id>")
def classic_level(level_id):
    level = find_classic_level(level_id)
    if level is None:
        abort(404)
    active_profile = get_active_profile(DATABASE_PATH)
    saved_progress = (
        list_classic_progress(DATABASE_PATH, active_profile["id"])
        if active_profile is not None else []
    )
    block = find_classic_block(
        level_id, get_classic_block_statuses(saved_progress)
    )
    if block is None or not block["unlocked"]:
        return render_template(
            "classic_locked.html", block=block, active_profile=active_profile
        ), 403
    return render_template(
        "classic_level.html",
        level=level,
        active_profile=active_profile,
    )


@app.route("/api/classic/results", methods=["POST"])
def submit_classic_result():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Send a JSON result."), 400

    level_id = payload.get("level_id")
    if type(level_id) is not int:
        return jsonify(error="Invalid Classic level ID."), 400
    level = find_classic_level(level_id)
    if level is None:
        return jsonify(error="Classic level not found."), 404

    active_profile = get_active_profile(DATABASE_PATH)
    if active_profile is None:
        return jsonify(error="Select an active profile before playing to save results."), 409
    submitted_profile_id = payload.get("profile_id")
    if type(submitted_profile_id) is not int or submitted_profile_id != active_profile["id"]:
        return jsonify(error="The active profile changed. This run was not saved."), 409

    saved_progress = list_classic_progress(DATABASE_PATH, active_profile["id"])
    block = find_classic_block(
        level_id, get_classic_block_statuses(saved_progress)
    )
    if block is None or not block["unlocked"]:
        return jsonify(error="This Classic level is locked."), 403

    typed_buffer = payload.get("typed_buffer")
    target = level["passage"]
    if not isinstance(typed_buffer, str) or len(typed_buffer) != len(target):
        return jsonify(error="The typed buffer must match the passage length."), 400
    if any(ord(character) < 32 or ord(character) == 127 for character in typed_buffer):
        return jsonify(error="The typed buffer contains an invalid character."), 400

    active_elapsed_ms = payload.get("active_elapsed_ms")
    if type(active_elapsed_ms) not in (int, float):
        return jsonify(error="Active elapsed time must be a positive number."), 400
    try:
        active_elapsed_ms = float(active_elapsed_ms)
    except OverflowError:
        return jsonify(error="Active elapsed time is too large."), 400
    if not math.isfinite(active_elapsed_ms) or active_elapsed_ms < 1:
        return jsonify(error="Active elapsed time must be at least 1 ms."), 400

    result = recompute_classic_result(typed_buffer, target, active_elapsed_ms)
    if not all(math.isfinite(result[key]) for key in ("raw_wpm", "accuracy", "net_wpm")):
        return jsonify(error="Active elapsed time is too small."), 400

    try:
        session_id, progress = save_classic_result(
            DATABASE_PATH, active_profile["id"], level_id, result
        )
    except ValueError as error:
        return jsonify(error=str(error)), 409

    return jsonify(
        saved=True,
        session_id=session_id,
        best_stars=progress["best_stars"],
        best_net_wpm=progress["best_net_wpm"],
    ), 201


@app.route("/progress")
def progress():
    active_profile = get_active_profile(DATABASE_PATH)
    if active_profile is None:
        return render_template("progress.html", active_profile=None)
    return render_template(
        "progress.html",
        active_profile=active_profile,
        total_classic_levels=len(load_classic_levels()),
        summary=get_classic_summary(DATABASE_PATH, active_profile["id"]),
        recent_sessions=list_recent_classic_sessions(DATABASE_PATH, active_profile["id"]),
    )


@app.route("/profiles")
def profiles():
    return profile_page()


@app.route("/profiles/create", methods=["POST"])
def create_profile_route():
    name = request.form.get("name", "")
    try:
        create_profile(DATABASE_PATH, name)
    except ValueError as error:
        return profile_page(error=str(error), entered_name=name), 400
    except sqlite3.IntegrityError:
        return profile_page(
            error="A profile with this name already exists.", entered_name=name
        ), 400
    return redirect(url_for("profiles"))


@app.route("/profiles/select", methods=["POST"])
def select_profile_route():
    profile_id = request.form.get("profile_id", type=int)
    if profile_id is None or not select_profile(DATABASE_PATH, profile_id):
        return profile_page(error="Select an existing profile."), 400
    return redirect(url_for("profiles"))


@app.route("/settings")
def settings():
    return render_template("settings.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
