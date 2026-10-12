from flask import Flask


def create_app():
  app = Flask(__name__)

  # Test route to verify server is working
  @app.route('/')
  def home():
    return 'CampusPulse Server is Up and Running!'

  return app