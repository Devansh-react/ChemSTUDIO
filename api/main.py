from fastapi import FastAPI

from api.routes import router


app = FastAPI(

    title="Chem Process Studio",

    version="1.0.0",

    description="""
Multi-Agent Chemical Reaction Prediction Platform
"""
)

app.include_router(router)


@app.get("/")
async def home():

    return {
        "message": "Chem Process Studio API Running"
    }