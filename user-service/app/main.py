from fastapi import FastAPI

app = FastAPI(title = "FoC User Service")

@app.get("/health")
def health_check():
    return {"status": "healthy"}
