import logging

from server import run_server

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    run_server()

if __name__ == "__main__":
    main()