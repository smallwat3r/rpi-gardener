from os import environ

from flask import Flask
from flask_sock import Sock

from rpi.lib.config import FLASK_SECRET_KEY

from .api import dashboard_api, health, pico
from .spa import spa
from .websockets import init_websockets

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = bool(environ.get("RELOAD"))
app.secret_key = FLASK_SECRET_KEY

app.register_blueprint(health)
app.register_blueprint(pico)
app.register_blueprint(dashboard_api)
app.register_blueprint(spa)

sock = Sock(app)
init_websockets(sock)
