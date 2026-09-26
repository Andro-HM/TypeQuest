import json
import sqlite3
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, url_for

from database import (
    create_profile,
    get_active_profile,
    initialize_database,
    list_profiles,
    select_profile,
)


app = Flask(__name__)
DATABASE_PATH = Path(app.instance_path) / "typequest.sqlite3"
CLASSIC_CONTENT_PATH = Path(app.root_path) / "content" / "classic.json"
initialize_database(DATABASE_PATH)


def load_classic_levels():
    with CLASSIC_CONTENT_PATH.open(encoding="ascii") as content_file:
        content = json.load(content_file)
    return content["levels"]


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
    return render_template("classic_levels.html", levels=load_classic_levels())


@app.route("/play/classic/<int:level_id>")
def classic_level(level_id):
    for level in load_classic_levels():
        if level["id"] == level_id:
            return render_template("classic_level.html", level=level)
    abort(404)


@app.route("/progress")
def progress():
    return render_template("progress.html")


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
