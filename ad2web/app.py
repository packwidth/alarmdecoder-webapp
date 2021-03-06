# -*- coding: utf-8 -*-

from gevent import monkey
monkey.patch_all()

import os
import signal
import jsonpickle

from flask import Flask, request, render_template, g, redirect, url_for
from flask.ext.babel import Babel
from flask.ext.script import Manager

from alarmdecoder import AlarmDecoder
from alarmdecoder.devices import SerialDevice

from .config import DefaultConfig
from .decoder import decodersocket, Decoder, create_decoder_socket
from .user import User, user
from .settings import settings
from .frontend import frontend
from .api import api
from .admin import admin
from .certificate import certificate
from .log import log
from .keypad import keypad
from .notifications import notifications
from .zones import zones
from .settings.models import Setting
from .setup.constants import SETUP_COMPLETE, SETUP_STAGE_ENDPOINT, SETUP_ENDPOINT_STAGE
from .setup import setup
from .updater import updater
from .extensions import db, mail, cache, login_manager, oid
from .utils import INSTANCE_FOLDER_PATH


# For import *
__all__ = ['create_app']

DEFAULT_BLUEPRINTS = (
    frontend,
    user,
    settings,
    api,
    admin,
    certificate,
    log,
    keypad,
    decodersocket,
    notifications,
    zones,
    setup,
    updater,
)

def create_app(config=None, app_name=None, blueprints=None):
    """Create a Flask app."""

    if app_name is None:
        app_name = DefaultConfig.PROJECT
    if blueprints is None:
        blueprints = DEFAULT_BLUEPRINTS

    app = Flask(app_name, instance_path=INSTANCE_FOLDER_PATH, instance_relative_config=True)
    configure_app(app, config)
    configure_hook(app)
    configure_blueprints(app, blueprints)
    configure_extensions(app)
    configure_logging(app)
    configure_template_filters(app)
    configure_error_handlers(app)

    appsocket = create_decoder_socket(app)
    decoder = Decoder(app, appsocket)
    manager = Manager(app)
    app.decoder = decoder

    def signal_handler(signal, frame):
        decoder.stop()
        os._exit(0)

    try:
        signal.signal(signal.SIGINT, signal_handler)

        decoder.start()
        decoder.init()

    except Exception, err:
        app.logger.error("Error", exc_info=True)

    return app, appsocket


def configure_app(app, config=None):
    """Different ways of configurations."""

    # http://flask.pocoo.org/docs/api/#configuration
    app.config.from_object(DefaultConfig)

    # http://flask.pocoo.org/docs/config/#instance-folders
    app.config.from_pyfile('production.cfg', silent=True)

    if config:
        app.config.from_object(config)

    # Use instance folder instead of env variables to make deployment easier.
    #app.config.from_envvar('%s_APP_CONFIG' % DefaultConfig.PROJECT.upper(), silent=True)


def configure_extensions(app):
    # flask-sqlalchemy
    db.init_app(app)

    # flask-mail
    mail.init_app(app)

    # flask-cache
    cache.init_app(app)

    # flask-babel
    babel = Babel(app)

    @babel.localeselector
    def get_locale():
        accept_languages = app.config.get('ACCEPT_LANGUAGES')
        return request.accept_languages.best_match(accept_languages)

    # flask-login
    login_manager.login_view = 'frontend.login'
    login_manager.refresh_view = 'frontend.reauth'

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(id)
    login_manager.setup_app(app)

    # flask-openid
    oid.init_app(app)


def configure_blueprints(app, blueprints):
    """Configure blueprints in views."""

    for blueprint in blueprints:
        app.register_blueprint(blueprint)


def configure_template_filters(app):

    @app.template_filter()
    def pretty_date(value):
        return pretty_date(value)

    @app.template_filter()
    def format_date(value, format='%Y-%m-%d'):
        return value.strftime(format)


def configure_logging(app):
    """Configure file(info) and email(error) logging."""

    import logging
    from logging.handlers import SMTPHandler

    # Set info level on logger, which might be overwritten by handers.
    # Suppress DEBUG messages.
    if app.config['DEBUG']:
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(logging.INFO)

    info_log = os.path.join(app.config['LOG_FOLDER'], 'info.log')
    info_file_handler = logging.handlers.RotatingFileHandler(info_log, maxBytes=100000, backupCount=10)
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]')
    )
    app.logger.addHandler(info_file_handler)


def configure_hook(app):
    safe_blueprints = ['setup', 'sock', None]   # None = static content.

    @app.before_request
    def before_request():
        if request.blueprint == 'setup':
            setup_stage = Setting.get_by_name('setup_stage').value
            # If setup hasn't been started, redirect to the index
            if setup_stage is None:
                if request.endpoint != 'setup.index' and request.endpoint != 'setup.type':
                    return redirect(url_for('setup.index'))

            # Disallow skipping ahead in the setup process but allow them to go back.
            elif SETUP_ENDPOINT_STAGE[request.endpoint] > setup_stage:
                return redirect(url_for(SETUP_STAGE_ENDPOINT[setup_stage]))

        elif not request.blueprint in safe_blueprints:
            setup_stage = Setting.get_by_name('setup_stage').value
            # If setup hasn't been started, force them to the index.
            if setup_stage is None:
                return redirect(url_for('setup.index'))

            # And if it has, place them at the last-known stage.
            elif setup_stage != SETUP_COMPLETE:
                stage_page = SETUP_STAGE_ENDPOINT[setup_stage]

                return redirect(url_for(stage_page))

        g.alarmdecoder = app.decoder


def configure_error_handlers(app):
    @app.errorhandler(403)
    def forbidden_page(error):
        return render_template("errors/forbidden_page.html"), 403

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/page_not_found.html"), 404

    @app.errorhandler(500)
    def server_error_page(error):
        return render_template("errors/server_error.html"), 500
