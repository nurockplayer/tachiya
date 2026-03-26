from fastapi import FastAPI

app = FastAPI(title="Tachiya API")


@app.get("/health")
def health():
    return {"status": "ok"}
