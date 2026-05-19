import logging
import sys

from globalshop_bi.simulator import run_simulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    try:
        run_simulator()
    except Exception as exc:
        logging.getLogger(__name__).error("Simulador terminou com erro: %s", exc, exc_info=True)
        sys.exit(1)
