"""NSP Learning Centre - Teacher Workload, KPI & Retention module (prototype).

Layers (see the architecture diagram in the report):
    presentation -> services -> domain
                        |-> data (repositories) -> SQLite
                        |-> integration (EduTizimGateway)
"""
from __future__ import annotations

from datetime import datetime

from flask import Flask

from .data import Database
from .data.seed import DemoSeeder
from .integration import DemoEduTizimGateway


def create_app(database_url: str = "sqlite:///nsp_demo.db", reseed: bool = True) -> Flask:
    app = Flask(__name__, template_folder="presentation/templates", static_folder="static")
    app.config["SECRET_KEY"] = "nsp-prototype-demo-key"

    database = Database(database_url)
    app.extensions["nsp_database"] = database

    def seed() -> None:
        database.reset()
        seeder = DemoSeeder(database.session(), datetime.now())
        app.extensions["nsp_gateway"] = seeder.run()
        database.session.remove()

    app.extensions["nsp_seed"] = seed
    if reseed:
        seed()
    else:
        database.create_all()
        app.extensions["nsp_gateway"] = DemoEduTizimGateway(datetime.now())

    from .presentation import register_presentation

    register_presentation(app)
    return app
