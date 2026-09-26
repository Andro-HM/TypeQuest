from flask import Flask, render_template


app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/play")
def play():
    return render_template("play.html")


@app.route("/progress")
def progress():
    return render_template("progress.html")


@app.route("/profiles")
def profiles():
    return render_template("profiles.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
