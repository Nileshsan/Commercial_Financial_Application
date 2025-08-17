import requests
import xmltodict
import json
import os
from dotenv import load_dotenv
import sys
import datetime
from tkinter import messagebox
import re
import html
from xml.etree import ElementTree as ET
import time
import socket
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

def print_log(msg, level="INFO"):
    """Terminal log printing for CLI feedback"""
    prefix = {
        "INFO": "[LOG]",
        "ERROR": "[ERROR]",
        "WARN": "[WARN]",
        "SUCCESS": "[SUCCESS]"
    }.get(level, "[LOG]")
    print(f"{prefix} {msg}")

# Logging setup
LOG_FILE = os.path.join(os.path.dirname(__file__), 'enhanced_sync_log.txt')
def log(msg, level="INFO"):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {msg}\n")
    except Exception as e:
        print_log(f"[LOG ERROR] Failed to write to log file: {e}", level="ERROR")
    print_log(msg, level)

load_dotenv()

if getattr(sys, 'frozen', False):
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
else:
    base_path = os.path.abspath(".")

env_path = os.path.join(base_path, 'config.env')
load_dotenv(dotenv_path=env_path)

TALLY_URL = os.getenv("TALLY_URL", "http://localhost:9000")
log(f"Loaded TALLY_URL: {TALLY_URL}")

# Connection configuration
MAX_RETRIES = 3
RETRY_DELAY = 2
CONNECTION_TIMEOUT = 15
READ_TIMEOUT = 120  # Increased timeout for large reports

def check_tally_service():
    """Check if Tally service is running on the specified port."""
    try:
        url_parts = TALLY_URL.replace('http://', '').replace('https://', '')
        host_port = url_parts.split('/')[0]
        host = host_port.split(':')[0]
        port = int(host_port.split(':')[1]) if ':' in host_port else 9000
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            log(f"✅ Tally service is running on {host}:{port}")
            return True
        else:
            log(f"❌ Tally service is not running on {host}:{port}")
            return False
    except Exception as e:
        log(f"❌ Error checking Tally service: {e}")
        return False

def create_session():
    """Create a requests session with appropriate settings."""
    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/xml',
        'User-Agent': 'EnhancedTallyConnector/1.0',
        'Connection': 'keep-alive'
    })
    return session

def send_tally_request(xml_request, return_json=False, max_retries=MAX_RETRIES):
    """Send XML request to Tally with retry logic."""
    if not TALLY_URL:
        log("❌ TALLY_URL is not set")
        return None
    
    if not check_tally_service():
        log("❌ Tally service is not available")
        return None
    
    last_error = None
    session = create_session()
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                log(f"Retry attempt {attempt + 1}/{max_retries}")
                time.sleep(RETRY_DELAY * attempt)
            
            response = session.post(
                TALLY_URL,
                data=xml_request.encode('utf-8'),
                timeout=(CONNECTION_TIMEOUT, READ_TIMEOUT)
            )
            
            if response.status_code == 200 and response.text.strip():
                # Check for Tally error patterns
                error_patterns = [
                    '<LINEERROR>', 'Error in TDL', 'Invalid Report', 
                    'Report not found', 'TDL Error', 'No such report'
                ]
                
                if any(err in response.text for err in error_patterns):
                    log(f"❌ Tally returned error: {response.text[:300]}...")
                    return None
                
                # Clean and parse the response
                cleaned_xml = clean_xml_data(response.text)
                
                try:
                    if return_json:
                        parsed_dict = xmltodict.parse(cleaned_xml)
                        return json.dumps(parsed_dict, indent=2, ensure_ascii=False)
                    else:
                        return xmltodict.parse(cleaned_xml)
                except Exception as parse_err:
                    log(f"❌ Parse error: {parse_err}")
                    last_error = parse_err
                    continue
            else:
                log(f"❌ HTTP error: {response.status_code}")
                last_error = f"HTTP {response.status_code}"
                continue
                
        except requests.exceptions.Timeout:
            log(f"❌ Timeout on attempt {attempt + 1}")
            last_error = "Timeout"
            continue
        except requests.exceptions.ConnectionError as e:
            log(f"❌ Connection error: {e}")
            last_error = f"Connection error: {e}"
            continue
        except Exception as e:
            log(f"❌ Unexpected error: {e}")
            last_error = f"Unexpected error: {e}"
            continue
    
    session.close()
    log(f"❌ All {max_retries} attempts failed. Last error: {last_error}")
    return None

def clean_xml_data(xml_str):
    """Clean and fix XML data from Tally."""
    if not xml_str:
        return ""
    
    # Remove invalid XML characters
    cleaned = re.sub(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]', '', xml_str)
    
    # Decode HTML entities
    cleaned = html.unescape(cleaned)
    
    # Fix common Tally XML issues
    cleaned = re.sub(r'&(?![a-zA-Z]+;)', '&amp;', cleaned)  # Fix unescaped ampersands
    cleaned = re.sub(r'<([^>]*?)>', lambda m: m.group(0).replace('&', '&amp;') if '&' in m.group(1) and '&amp;' not in m.group(1) else m.group(0), cleaned)
    
    # Ensure proper XML declaration
    if not cleaned.strip().startswith('<?xml'):
        cleaned = '<?xml version="1.0" encoding="UTF-8"?>\n' + cleaned
    
    return cleaned

def get_company_name():
    """Get the current company name from Tally (robust, always returns human-readable name)."""
    xml_request = """
    <ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>List of Accounts</REPORTNAME>
                    <STATICVARIABLES>
                        <ACCOUNTTYPE>Company</ACCOUNTTYPE>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>
    """
    data = send_tally_request(xml_request)
    if not data:
        return None
    try:
        # Try different paths to find company name
        paths_to_try = [
            ['ENVELOPE', 'BODY', 'DATA', 'TALLYMESSAGE', 'COMPANY', '@NAME'],
            ['ENVELOPE', 'BODY', 'DATA', 'TALLYMESSAGE', 'COMPANY', 'NAME'],
            ['ENVELOPE', 'BODY', 'DATA', 'COMPANY', '@NAME'],
            ['ENVELOPE', 'BODY', 'DATA', 'COMPANY', 'NAME'],
            ['ENVELOPE', 'COMPANY', '@NAME'],
            ['ENVELOPE', 'COMPANY', 'NAME'],
            ['COMPANY', '@NAME'],
            ['COMPANY', 'NAME']
        ]
        for path in paths_to_try:
            try:
                current = data
                for key in path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        break
                else:
                    if isinstance(current, str) and current.strip():
                        return current.strip()
            except:
                continue
        # Fallback: search recursively
        def find_company_name(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if 'COMPANY' in key.upper() or 'NAME' in key.upper():
                        if isinstance(value, str) and value.strip():
                            return value.strip()
                        elif isinstance(value, dict):
                            result = find_company_name(value)
                            if result:
                                return result
                    else:
                        result = find_company_name(value)
                        if result:
                            return result
            elif isinstance(obj, list):
                for item in obj:
                    result = find_company_name(item)
                    if result:
                        return result
            return None
        return find_company_name(data)
    except Exception as e:
        log(f"❌ Error extracting company name: {e}")
        return None

def fetch_client_ledgers():
    """Fetch all client ledgers (Sundry Debtors and Sundry Creditors)."""
    xml_request = """
    <ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>List of Accounts</REPORTNAME>
                    <STATICVARIABLES>
                        <ACCOUNTTYPE>All Ledgers</ACCOUNTTYPE>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>
    """
    
    log("Fetching client ledgers")
    result = send_tally_request(xml_request)
    
    if result and 'ENVELOPE' in result:
        try:
            client_ledgers = []
            
            def extract_ledgers(obj):
                if isinstance(obj, dict):
                    if 'LEDGER' in obj:
                        ledgers = obj['LEDGER'] if isinstance(obj['LEDGER'], list) else [obj['LEDGER']]
                        for ledger in ledgers:
                            if isinstance(ledger, dict):
                                # Check if it's a client ledger (Sundry Debtors/Creditors)
                                parent = ledger.get('PARENT', '')
                                name = ledger.get('NAME', '')
                                
                                if ('Sundry Debtors' in parent or 'Sundry Creditors' in parent or 
                                    'Sundry Debtors' in name or 'Sundry Creditors' in name):
                                    client_ledgers.append({
                                        'name': name,
                                        'parent': parent,
                                        'opening_balance': ledger.get('OPENINGBALANCE', '0'),
                                        'opening_balance_type': ledger.get('OPENINGBALANCETYPE', ''),
                                        'closing_balance': ledger.get('CLOSINGBALANCE', '0'),
                                        'closing_balance_type': ledger.get('CLOSINGBALANCETYPE', '')
                                    })
                    
                    for value in obj.values():
                        if isinstance(value, (dict, list)):
                            extract_ledgers(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_ledgers(item)
            
            extract_ledgers(result)
            log(f"✅ Found {len(client_ledgers)} client ledgers")
            return client_ledgers
        except Exception as e:
            log(f"❌ Error parsing client ledgers: {e}")
            return []
    else:
        log("❌ Invalid response format for client ledgers")
        return []

def fetch_client_transactions():
    """Fetch all transactions for client ledgers with detailed information (no date filter)."""
    xml_request = f"""
    <ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>Ledger Vouchers</REPORTNAME>
                    <STATICVARIABLES>
                        <EXPLODEFLAG>Yes</EXPLODEFLAG>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>
    """
    
    log(f"Fetching client transactions (no date filter)")
    result = send_tally_request(xml_request)
    
    if result and 'ENVELOPE' in result:
        try:
            client_transactions = []
            
            def extract_transactions(obj):
                if isinstance(obj, dict):
                    if 'VOUCHER' in obj:
                        vouchers = obj['VOUCHER'] if isinstance(obj['VOUCHER'], list) else [obj['VOUCHER']]
                        for voucher in vouchers:
                            if isinstance(voucher, dict):
                                # Extract transaction details
                                transaction = {
                                    'date': voucher.get('DATE', ''),
                                    'voucher_type': voucher.get('VOUCHERTYPENAME', ''),
                                    'voucher_number': voucher.get('VOUCHERNUMBER', ''),
                                    'party_name': voucher.get('PARTYLEDGERNAME', ''),
                                    'amount': voucher.get('AMOUNT', '0'),
                                    'narration': voucher.get('NARRATION', ''),
                                    'debit_amount': voucher.get('DEBITAMOUNT', '0'),
                                    'credit_amount': voucher.get('CREDITAMOUNT', '0'),
                                    'balance': voucher.get('BALANCE', '0'),
                                    'balance_type': voucher.get('BALANCETYPE', '')
                                }
                                client_transactions.append(transaction)
                    
                    for value in obj.values():
                        if isinstance(value, (dict, list)):
                            extract_transactions(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_transactions(item)
            
            extract_transactions(result)
            log(f"✅ Found {len(client_transactions)} client transactions")
            return client_transactions
        except Exception as e:
            log(f"❌ Error parsing client transactions: {e}")
            return []
    else:
        log("❌ Invalid response format for client transactions")
        return []

def fetch_specific_client_ledger(client_name):
    """Fetch detailed ledger for a specific client (no date filter)."""
    xml_request = f"""
    <ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>Ledger</REPORTNAME>
                    <STATICVARIABLES>
                        <SVLEDGERNAME>{client_name}</SVLEDGERNAME>
                        <EXPLODEFLAG>Yes</EXPLODEFLAG>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>
    """
    
    log(f"Fetching detailed ledger for client: {client_name} (no date filter)")
    result = send_tally_request(xml_request)
    
    if result and 'ENVELOPE' in result:
        try:
            ledger_details = {
                'client_name': client_name,
                'opening_balance': '0',
                'opening_balance_type': '',
                'closing_balance': '0',
                'closing_balance_type': '',
                'transactions': []
            }
            
            def extract_ledger_details(obj):
                if isinstance(obj, dict):
                    if 'LEDGER' in obj:
                        ledger = obj['LEDGER']
                        if isinstance(ledger, dict):
                            ledger_details['opening_balance'] = ledger.get('OPENINGBALANCE', '0')
                            ledger_details['opening_balance_type'] = ledger.get('OPENINGBALANCETYPE', '')
                            ledger_details['closing_balance'] = ledger.get('CLOSINGBALANCE', '0')
                            ledger_details['closing_balance_type'] = ledger.get('CLOSINGBALANCETYPE', '')
                    
                    if 'VOUCHER' in obj:
                        vouchers = obj['VOUCHER'] if isinstance(obj['VOUCHER'], list) else [obj['VOUCHER']]
                        for voucher in vouchers:
                            if isinstance(voucher, dict):
                                transaction = {
                                    'date': voucher.get('DATE', ''),
                                    'voucher_type': voucher.get('VOUCHERTYPENAME', ''),
                                    'voucher_number': voucher.get('VOUCHERNUMBER', ''),
                                    'amount': voucher.get('AMOUNT', '0'),
                                    'debit_amount': voucher.get('DEBITAMOUNT', '0'),
                                    'credit_amount': voucher.get('CREDITAMOUNT', '0'),
                                    'balance': voucher.get('BALANCE', '0'),
                                    'balance_type': voucher.get('BALANCETYPE', ''),
                                    'narration': voucher.get('NARRATION', '')
                                }
                                ledger_details['transactions'].append(transaction)
                    
                    for value in obj.values():
                        if isinstance(value, (dict, list)):
                            extract_ledger_details(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_ledger_details(item)
            
            extract_ledger_details(result)
            log(f"✅ Found {len(ledger_details['transactions'])} transactions for {client_name}")
            return ledger_details
        except Exception as e:
            log(f"❌ Error parsing ledger details: {e}")
            return None
    else:
        log("❌ Invalid response format for ledger details")
        return None

def fetch_comprehensive_client_data():
    """Fetch comprehensive client data including ledgers and transactions (no date filter)."""
    log(f"🔍 Fetching comprehensive client data (no date filter)")
    
    try:
        # Get company name
        company_name = get_company_name()
        
        # Get all client ledgers
        client_ledgers = fetch_client_ledgers()
        
        # Get detailed data for each client
        comprehensive_data = {
            "company_name": company_name,
            "export_date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "export_time": datetime.datetime.now().strftime("%H:%M:%S"),
            "clients": []
        }
        
        for ledger in client_ledgers:
            client_name = ledger['name']
            log(f"Processing client: {client_name}")
            
            # Get detailed ledger for this client
            client_details = fetch_specific_client_ledger(client_name)
            
            if client_details:
                comprehensive_data['clients'].append({
                    'ledger_info': ledger,
                    'detailed_ledger': client_details
                })
            else:
                # Add basic ledger info if detailed fetch failed
                comprehensive_data['clients'].append({
                    'ledger_info': ledger,
                    'detailed_ledger': {
                        'client_name': client_name,
                        'opening_balance': ledger['opening_balance'],
                        'opening_balance_type': ledger['opening_balance_type'],
                        'closing_balance': ledger['closing_balance'],
                        'closing_balance_type': ledger['closing_balance_type'],
                        'transactions': []
                    }
                })
        
        log(f"✅ Successfully processed {len(comprehensive_data['clients'])} clients")
        return comprehensive_data
        
    except Exception as e:
        log(f"❌ Error in comprehensive client data: {e}")
        return None

def export_client_data_to_json(data, filename=None):
    """Export client data to JSON file."""
    if not filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"client_data_export_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log(f"✅ Data exported to {filename}")
        return filename
    except Exception as e:
        log(f"❌ Error exporting data: {e}")
        return None

def fetch_all_transactions(start_date, end_date, voucher_types=None):
    """
    Fetch all transactions (sales, purchase, receipt, payment, etc.) for the loaded company from the Day Book.
    Optionally filter by voucher_types (list of strings, e.g. ['Sales', 'Purchase']).
    Returns a list of transactions (dicts).
    """
    xml_request = f"""
    <ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>Day Book</REPORTNAME>
                    <STATICVARIABLES>
                        <SVFROMDATE>{start_date}</SVFROMDATE>
                        <SVTODATE>{end_date}</SVTODATE>
                        <EXPLODEFLAG>Yes</EXPLODEFLAG>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>
    """
    log(f"Fetching all transactions from {start_date} to {end_date} (Day Book)")
    result = send_tally_request(xml_request)
    transactions = []
    if result and 'ENVELOPE' in result:
        try:
            def extract_vouchers(obj):
                if isinstance(obj, dict):
                    if 'VOUCHER' in obj:
                        vouchers = obj['VOUCHER'] if isinstance(obj['VOUCHER'], list) else [obj['VOUCHER']]
                        for voucher in vouchers:
                            if isinstance(voucher, dict):
                                # Basic transaction info
                                txn = {
                                    'date': voucher.get('DATE', ''),
                                    'voucher_type': voucher.get('VOUCHERTYPENAME', ''),
                                    'voucher_number': voucher.get('VOUCHERNUMBER', ''),
                                    'party_name': voucher.get('PARTYLEDGERNAME', ''),
                                    'amount': voucher.get('AMOUNT', '0'),
                                    'narration': voucher.get('NARRATION', ''),
                                    'all_fields': voucher  # Keep all fields for advanced use
                                }
                                transactions.append(txn)
                    for value in obj.values():
                        if isinstance(value, (dict, list)):
                            extract_vouchers(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_vouchers(item)
            extract_vouchers(result)
            # Optional filtering by voucher type
            if voucher_types:
                voucher_types_lower = [v.lower() for v in voucher_types]
                filtered = [txn for txn in transactions if txn['voucher_type'].lower() in voucher_types_lower]
                log(f"Filtered {len(filtered)} transactions by voucher_types={voucher_types}")
                return filtered
            log(f"Fetched {len(transactions)} transactions from Day Book")
            return transactions
        except Exception as e:
            log(f"❌ Error parsing transactions: {e}")
            return []
    else:
        log("❌ Invalid response format for Day Book")
        return []

def test_enhanced_connector():
    """Test the enhanced Tally connector functionality."""
    log("🧪 Testing Enhanced Tally Connector")
    
    # Test basic connection
    if not check_tally_service():
        log("❌ Tally service not available")
        return False
    
    # Test company name
    company_name = get_company_name()
    if not company_name:
        log("❌ Could not fetch company name")
        return False
    
    log(f"✅ Connected to company: {company_name}")
    
    # Test client ledgers
    client_ledgers = fetch_client_ledgers()
    if not client_ledgers:
        log("❌ No client ledgers found")
        return False
    
    log(f"✅ Found {len(client_ledgers)} client ledgers")
    
    # Test comprehensive data fetch
    comprehensive_data = fetch_comprehensive_client_data()
    if not comprehensive_data:
        log("❌ Could not fetch comprehensive data")
        return False
    
    log(f"✅ Successfully fetched comprehensive data for {len(comprehensive_data['clients'])} clients")
    
    # Export test data
    export_filename = export_client_data_to_json(comprehensive_data)
    if export_filename:
        log(f"✅ Test data exported to {export_filename}")
    
    return True

if __name__ == "__main__":
    test_enhanced_connector() 