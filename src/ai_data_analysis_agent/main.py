from fastapi import FastAPI
from ai_data_analysis_agent.api.routes import query, file_upload, session

app = FastAPI(
    title="AI Agent System",
    version="0.1.0"
)

@app.get("/")
def root():
    return {"status": "ok"}

app.include_router(query.router)
app.include_router(file_upload.router)
app.include_router(session.router)