import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation.offline import format_report, write_report

if __name__ == "__main__":
    report = write_report(Path("offline-evaluation.json"))
    print(format_report(report))
