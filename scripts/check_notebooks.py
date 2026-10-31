"""Execute all four notebooks with the active interpreter and save real outputs."""
from pathlib import Path
import sys
import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parents[1]
for path in sorted((root / 'notebooks').glob('*.ipynb')):
    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(notebook, timeout=120, kernel_name='python3',
                            resources={'metadata': {'path': str(root / 'notebooks')}})
    # Keep kernel setup local to this invocation; do not install a user-wide kernel.
    manager = client.create_kernel_manager()
    manager.kernel_spec.argv = [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']
    client.km = manager
    client.execute()
    assert not any(output.output_type == 'error' for cell in notebook.cells if cell.cell_type == 'code'
                   for output in cell.outputs)
    nbformat.validate(notebook)
    nbformat.write(notebook, path)
    print(f'PASS {path.name}', flush=True)
