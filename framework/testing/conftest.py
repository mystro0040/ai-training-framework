import sys
from pathlib import Path

# Make the platform/ dir importable so `import ratingkit` works under pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
