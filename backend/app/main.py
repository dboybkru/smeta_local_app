from fastapi import FastAPI

app = FastAPI(title="SmetaApp API")


@app.get("/api/health")
def health():
    return {"status": "ok"}
