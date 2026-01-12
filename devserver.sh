#!/usr/bin/env bash
# Simple dev server launcher for Flask
export FLASK_APP=main.py
export FLASK_ENV=development
flask run --host=0.0.0.0 --port=5000
