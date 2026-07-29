import sys
import uvicorn

# Add project root to path
sys.path.insert(0, "/home/martinferreirab/proyectos/enbici")

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )
