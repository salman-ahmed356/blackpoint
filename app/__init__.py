import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import click

from dotenv import load_dotenv
from flask import Flask, request
from flask_babel import Babel

from .database import db, migrate
from .models import (
    Address, Agent, Appointment, Branch, Company, Customer, Package,
    Report, Staff, Vehicle, VehicleOwner, ExpertiseType,
    ExpertiseFeature, ExpertiseReport, PackageExpertise
)
from .services.commands import register_commands
from .services.expertise_initializer import ExpertiseInitializer
from .tests.test_config import TestConfig
from .services.company_service import create_default_company
from .services.package_service import create_default_package

# Blueprints
from .routes.appointments import appointments as appointments_bp
from .routes.customers import customers as customers_bp
from .routes.reports import reports as reports_bp
from .routes.staffs import staff as staff_bp
from .routes.main import main as main_bp
from .routes.branches import branches as branches_bp
from .routes.companies import companies as companies_bp
from .routes.errors import errors as errors_bp
from .routes.packages import packages as packages_bp
from .routes.pdfs import pdfs as pdfs_bp

# 1) Instantiate Babel once (no app yet)
babel = Babel()

# 2) Your standalone locale‐selector
def get_locale():
    return request.args.get('lang', 'en')


def create_app(config_object=None):
    # 3) Load .env / .flaskenv
    load_dotenv()

    # 4) Create Flask app
    app = Flask(
        __name__,
        static_url_path='/static',
        static_folder='static'
    )

    # 5) Initialize Babel (Flask-Babel 4.x style)
    babel.init_app(app, locale_selector=get_locale)

    # 6) Inject get_locale into Jinja so your templates can still call {{ get_locale() }}
    @app.context_processor
    def inject_get_locale():
        return {'get_locale': get_locale}

    # 7) Configure app
    if config_object == 'testing':
        app.config.from_object(TestConfig)
        app.logger.setLevel(logging.DEBUG)
    else:
        app.config.update(
            SECRET_KEY=os.getenv('SECRET_KEY', 'fallback-secret-key'),
            SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///data.db'),
            SQLALCHEMY_TRACK_MODIFICATIONS=False
        )

        # Logging setup
        os.makedirs('logs', exist_ok=True)
        file_handler = RotatingFileHandler(
            'logs/error.log', maxBytes=10_240, backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        app.logger.addHandler(stream_handler)

    logging.getLogger('fontTools.subset').setLevel(logging.WARNING)

    # 8) Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # 9) Register custom CLI commands
    register_commands(app)

    @app.cli.command("seed-data")
    def seed_data():
        """Populate expertise types, default company & package."""
        ExpertiseInitializer.initialize_expertise_reports()
        create_default_company()
        create_default_package()
        click.echo("✔️  Database seeded")

    # 10) Register blueprints
    app.register_blueprint(pdfs_bp)
    app.register_blueprint(packages_bp)
    app.register_blueprint(errors_bp)
    app.register_blueprint(branches_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(main_bp)

    return app
