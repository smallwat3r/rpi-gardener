from os import environ

from flask import Flask
from flask_sock import Sock

from rpi.lib.config import FLASK_SECRET_KEY

from .api import pico
from .views import dashboard
from .websockets import init_websockets

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = bool(environ.get("RELOAD"))
app.secret_key = FLASK_SECRET_KEY
app.register_blueprint(pico)
app.register_blueprint(dashboard)

sock = Sock(app)
init_websockets(sock)
