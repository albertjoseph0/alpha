import os, sys, pathlib
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "round5"))
DATA = ROOT / "data" / "round7" / "j10_merger_arb"
HERE = pathlib.Path(__file__).resolve().parent
DATA.mkdir(parents=True, exist_ok=True)
AGENT = "j10"
from sec import get  # noqa
