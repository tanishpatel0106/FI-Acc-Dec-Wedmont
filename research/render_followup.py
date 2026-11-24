"""Execute and render the report with this Python interpreter and isolated Jupyter configuration."""
import json
import argparse
import sys
import tempfile
from pathlib import Path

import nbformat
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient
from nbconvert import HTMLExporter
from traitlets.config import Config

sys.stdout.reconfigure(encoding="utf-8")

parser = argparse.ArgumentParser()
parser.add_argument("--notebook", type=Path)
args = parser.parse_args()
path = args.notebook or Path(__file__).resolve().parent / "followup_2026_11_19/fixed_income_validation.ipynb"
path = path.resolve()
folder = path.parent
notebook = nbformat.read(path, as_version=4)
with tempfile.TemporaryDirectory(prefix="lifecycle-report-kernel-") as temp:
    kernel = Path(temp) / "followup"
    kernel.mkdir()
    (kernel / "kernel.json").write_text(json.dumps({
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "LIFECYCLE report", "language": "python"}), encoding="utf-8")
    manager = KernelManager(kernel_name="followup", kernel_spec_manager=KernelSpecManager(kernel_dirs=[temp]))
    client = NotebookClient(notebook, km=manager, timeout=300, resources={"metadata": {"path": str(folder)}})
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
nbformat.write(notebook, path)
exporter = HTMLExporter(config=Config(), template_name="lab")
html, _ = exporter.from_notebook_node(notebook, resources={"metadata": {"name": "Fixed-income allocation validation"}})
path.with_suffix(".html").write_text(html, encoding="utf-8")
print("Executed and rendered", path)
