import sys
import uvicorn

# Add project root to path
sys.path.insert(0, "/home/martinferreirab/proyectos/enbici")

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
