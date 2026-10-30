import os
import tempfile

# CI uses synthetic fixtures only (no WRDS data); every test gets an isolated data dir
_TMP = tempfile.mkdtemp(prefix="lifecycle-test-")
os.environ["LIFECYCLE_SYNTHETIC"] = "1"
os.environ["LIFECYCLE_DATA_DIR"] = _TMP
