"""CLI for starting a local operator console."""
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="DemandRadar Pro — human-reviewed public opportunities")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    uvicorn.run("demandradar.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
