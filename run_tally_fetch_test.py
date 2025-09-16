import sys, traceback
from importlib import util

MODULE_PATH = r"C:\Users\Admin\Nilesh_Projects\CFA\cfa_ai_app\Desktop_tally_sync-agent\tally_connector.py"
spec = util.spec_from_file_location('tally_connector_test', MODULE_PATH)
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)

fetch = getattr(mod, 'fetch_ledger_opening_balances')
company = "Fluidtecq Pneumatics Private Limited (2022-23)"
try:
    print('Calling fetch_ledger_opening_balances...')
    res = fetch(company)
    print('Returned:', type(res), len(res) if isinstance(res, list) else res)
    import json
    try:
        print(json.dumps(res[:5], indent=2, ensure_ascii=False))
    except Exception:
        pass
except Exception as e:
    print('EXCEPTION:')
    traceback.print_exc()
    raise
