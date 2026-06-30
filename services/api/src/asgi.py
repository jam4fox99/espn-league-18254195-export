from fastapi import FastAPI

from mygm_api.main import create_app

app: FastAPI = create_app()
