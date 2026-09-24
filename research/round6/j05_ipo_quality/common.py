import os, sys, pathlib
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "round5"))
DATA = ROOT / "data" / "round6" / "j05_ipo_quality"
HERE = pathlib.Path(__file__).resolve().parent
DATA.mkdir(parents=True, exist_ok=True)
from sec import get  # noqa
