from fastapi import FastAPI

from api.routes import router
from api.auth_routes import router as auth_router


app = FastAPI(

    title="Chem Process Studio",

    version="1.0.0",

    description="""
Multi-Agent Chemical Reaction Prediction Platform
"""
)

app.include_router(router)
app.include_router(auth_router)


@app.get("/")
async def home():

    return {
        "message": "Chem Process Studio API Running"
    }