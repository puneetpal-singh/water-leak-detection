"""Exercise every Streamlit page against the generated local experiment."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

root = Path(__file__).resolve().parents[1]
app = AppTest.from_file(str(root / 'dashboard/app.py')).run(timeout=60)
assert not app.exception, app.exception
for page in ['Operating patterns', 'Sensor explorer', 'Leak event explorer',
             'Model comparison', 'Network & relationships']:
    app.sidebar.radio[0].set_value(page).run(timeout=60)
    assert not app.exception, f'{page}: {app.exception}'
    print(f'PASS {page}', flush=True)
print('PASS Overview and all five additional views', flush=True)
