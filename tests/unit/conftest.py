import pytest
from flask import Flask

pytestmark = pytest.mark.unit


@pytest.fixture(scope="session", autouse=True)
def app():
    unit_app = Flask(__name__)
    unit_app.config["TESTING"] = True
    return unit_app
