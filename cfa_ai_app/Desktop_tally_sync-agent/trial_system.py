import requests
import xml.etree.ElementTree as ET

def get_ledger_balances(date='20250801'):  # Format: YYYYMMDD
    url = "http://localhost:9000"

    # XML Request Envelope for Trial Balance
    xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
    <ENVELOPE>
        <HEADER>
            <VERSION>1</VERSION>
            <TALLYREQUEST>Export</TALLYREQUEST>
            <TYPE>Data</TYPE>
            <ID>Trial Balance</ID>
        </HEADER>
        <BODY>
            <DESC>
                <STATICVARIABLES>
                    <SVEXPORTFORMAT> Fluidtecq Pneumatics Private Limited (2022-23) </SVEXPORTFORMAT>
                    <SVFROMDATE>{date}</SVFROMDATE>
                    <SVTODATE>{date}</SVTODATE>
                </STATICVARIABLES>
            </DESC>
        </BODY>
    </ENVELOPE>"""

    headers = {"Content-Type": "application/xml"}

    try:
        response = requests.post(url, data=xml_request.encode('utf-8'), headers=headers)
        response.raise_for_status()

        # Parse XML response
        root = ET.fromstring(response.text)
        ledger_balances = {}

        for ledger in root.findall('.//GROUP.LIST/LEDGER.LIST'):
            name_elem = ledger.find('LEDGERNAME')
            balance_elem = ledger.find('CLOSINGBALANCE')
            if name_elem is not None and balance_elem is not None:
                name = name_elem.text.strip()
                balance_text = balance_elem.text.strip().replace(',', '')
                # Convert balance to float or int
                try:
                    if balance_text.endswith('Dr'):
                        amount = float(balance_text.replace('Dr', '').strip())
                    elif balance_text.endswith('Cr'):
                        amount = -float(balance_text.replace('Cr', '').strip())
                    else:
                        amount = float(balance_text)
                    ledger_balances[name] = amount
                except ValueError:
                    ledger_balances[name] = balance_text  # fallback to raw text

        return ledger_balances

    except requests.exceptions.RequestException as e:
        print(f"❌ Connection Error: {e}")
        return None
    except ET.ParseError as e:
        print(f"❌ XML Parse Error: {e}")
        return None

# 🔽 Run the function and print output
balances = get_ledger_balances()

if balances:
    for ledger, amount in balances.items():
        print(f"{ledger:40s} : {amount:,.2f}")
else:
    print("No ledger balances retrieved.")