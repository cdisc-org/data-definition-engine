"""``python -m pipeline --study <pipeline.yaml>`` from ``src/``."""
import sys

from pipeline.run_pipeline import main

sys.exit(main())
