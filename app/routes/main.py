from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/runs/<int:run_id>")
def run_detail(run_id: int):
    return render_template("run.html", run_id=run_id)
