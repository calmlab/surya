#!/usr/bin/env python3
"""
Surya FastAPI Server Runner

Usage:
    python surya/scripts/run_api.py --reload
    python surya/scripts/run_api.py --host 0.0.0.0 --port 8001 --workers 4
"""
import click
import uvicorn


@click.command()
@click.option('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
@click.option('--port', default=8001, type=int, help='Server port (default: 8001)')
@click.option('--reload', is_flag=True, help='Enable auto-reload (development mode)')
@click.option('--workers', default=1, type=int, help='Number of workers (default: 1)')
def main(host, port, reload, workers):
    """Start Surya FastAPI server"""
    print(f"Starting Surya API Server: http://{host}:{port}")
    print(f"API documentation: http://{host}:{port}/docs")
    print(f"Alternative docs: http://{host}:{port}/redoc")
    print()

    uvicorn.run(
        "surya.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1
    )


if __name__ == "__main__":
    main()
