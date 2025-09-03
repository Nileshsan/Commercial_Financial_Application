import sys, traceback
from importlib import util

MODULE_PATH = r"C:\Users\Admin\Nilesh_Projects\CFA\cfa_ai_app\Desktop_tally_sync-agent\api_connector.py"
spec = util.spec_from_file_location('api_connector_test', MODULE_PATH)
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)

APIConnector = getattr(mod, 'APIConnector')

try:
    c = APIConnector()
    sample = [{
        'date': '20250101',
        'voucher_type': 'test',
        'voucher_number': 'T1',
        'party_name': 'Test Party',
        'entries': [
            {'ledger_name': 'Cash', 'amount': 100.0, 'type': 'Asset'}
        ]
    }]
    ok = c.send_data_to_backend('vouchers', sample, is_json=False)
    print('send_data_to_backend returned:', ok)
except Exception as e:
    print('EXCEPTION:')
    traceback.print_exc()
    raise
