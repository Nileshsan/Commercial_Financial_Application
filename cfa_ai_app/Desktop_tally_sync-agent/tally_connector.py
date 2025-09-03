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

# --- Make sanitize_xml available globally ---
def sanitize_xml(xml_string):
    """Clean XML string to remove invalid characters and fix entities."""
    if not xml_string:
        return ""
    # Keep valid XML characters
    xml_string = ''.join(char for char in xml_string if
                        char in '\t\n\r' or
                        '\x20' <= char <= '\uD7FF' or
                        '\uE000' <= char <= '\uFFFD' or
                        '\U00010000' <= char <= '\U0010FFFF')
    # Fix unescaped ampersands
    xml_string = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;)', '&amp;', xml_string)
    return xml_string

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
except ImportError:
    from tkinter import Tk, messagebox
    root = Tk()
    root.withdraw()
    messagebox.showerror(
        "Missing Dependency",
        "The required package 'tenacity' is not installed.\n"
        "Please install it using 'pip install tenacity' and restart the application."
    )
    raise

import re
import html
from dateutil import parser, rrule
from datetime import timedelta

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
LOG_FILE = os.path.join(os.path.dirname(__file__), 'sync_log.txt')
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
READ_TIMEOUT = 120

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
        'User-Agent': 'TallyConnector/1.0',
        'Connection': 'keep-alive'
    })
    return session

def test_tally_connection():
    """Test if Tally is reachable using a simple company info request."""
    if not check_tally_service():
        return False
    
    test_request = """
    <ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>Ledger</REPORTNAME>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY> 
    </ENVELOPE>
    """
    
    if not TALLY_URL:
        log("❌ TALLY_URL is not set")
        return False
    
    try:
        log(f"Testing connection to {TALLY_URL}")
        session = create_session()
        response = session.post(
            TALLY_URL, 
            data=test_request.encode('utf-8'),
            timeout=(CONNECTION_TIMEOUT, READ_TIMEOUT)
        )
        
        log(f"Test response: status={response.status_code}, length={len(response.text)}")
        
        if response.status_code == 200 and response.text.strip():
            if any(pattern in response.text for pattern in ['<ENVELOPE>', '<TALLYMESSAGE>', '<COMPANY>', '<NAME>']):
                log("✅ Tally connection test successful")
                return True
            else:
                log(f"❌ Unexpected response format: {response.text[:200]}...")
                return False
        else:
            log(f"❌ HTTP error: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        log("❌ Connection timeout")
        return False
    except requests.exceptions.ConnectionError as e:
        log(f"❌ Connection error: {e}")
        return False
    except Exception as e:
        log(f"❌ Unexpected error: {e}")
        return False
    finally:
        try:
            session.close()
        except:
            pass

def clean_xml_data(xml_str):
    """Clean and fix XML data for proper parsing with enhanced error handling."""
    if not xml_str:
        return ""
    
    try:
        # Remove invalid XML characters using a whitelist approach
        cleaned = ''.join(char for char in xml_str if
                         char in '\t\n\r' or
                         '\x20' <= char <= '\uD7FF' or
                         '\uE000' <= char <= '\uFFFD' or
                         '\U00010000' <= char <= '\U0010FFFF')
        
        # Unescape HTML entities safely
        try:
            cleaned = html.unescape(cleaned)
        except Exception as e:
            log(f"HTML unescape warning: {e}", level="WARN")
        
        # Fix unescaped ampersands while preserving valid entities
        cleaned = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;|#\d+;|#x[0-9a-fA-F]+;)', '&amp;', cleaned)
        
        # Remove ASCII control characters except valid whitespace
        cleaned = ''.join(char for char in cleaned if char >= '\x20' or char in '\t\n\r')
        
        # Ensure proper XML declaration
        if not cleaned.strip().startswith('<?xml'):
            cleaned = '<?xml version="1.0" encoding="UTF-8"?>\n' + cleaned
        
        # Fix common XML issues
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)  # Remove control chars
        cleaned = re.sub(r']]>', ']]&gt;', cleaned)  # Fix CDATA end markers
        cleaned = re.sub(r'[\u0000-\u0008\u000B\u000C\u000E-\u001F]', '', cleaned)  # Remove more control chars
        
        return cleaned
        
    except Exception as e:
        log(f"XML cleaning error: {e}", level="ERROR")
        # Return minimal valid XML if cleaning fails
        return '<?xml version="1.0" encoding="UTF-8"?><ROOT/>'

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=RETRY_DELAY, max=10),
    retry=retry_if_exception_type((
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.RequestException
    ))
)
def send_tally_request(xml_request):
    """Send XML request to Tally and return parsed response or recoverable vouchers on XML error.
    
    Args:
        xml_request (str): The XML request to send to Tally.
        
    Returns:
        dict: Parsed XML response or recovered vouchers on error.
        
    Raises:
        requests.exceptions.RequestException: For unrecoverable HTTP errors.
    """
    url = os.getenv("TALLY_URL", "http://localhost:9000")
    headers = {
        'Content-Type': 'application/xml',
        'Accept': 'application/xml',
        'Connection': 'keep-alive'
    }
    try:
        response = requests.post(
            url,
            data=xml_request.encode('utf-8'),
            headers=headers,
            timeout=(CONNECTION_TIMEOUT, READ_TIMEOUT)
        )
        if response.status_code == 200:
            # Save raw response for debugging
            try:
                with open("raw_tally_response.xml", "w", encoding="utf-8") as f:
                    f.write(response.text)
            except Exception as file_err:
                log(f"File write error (raw_tally_response.xml): {file_err}")
            # Clean and parse XML
            cleaned_xml = clean_xml_data(response.text)
            try:
                return xmltodict.parse(cleaned_xml)
            except Exception as e:
                log(f"❌ XML Parse error: {e}")
                log(f"Raw response: {response.text[:500]}...")
                # --- Enhanced recovery: extract <VOUCHER> blocks ---
                voucher_blocks = re.findall(r'<VOUCHER[\s\S]*?</VOUCHER>', response.text)
                recovered = 0
                skipped = 0
                vouchers = []
                for vb in voucher_blocks:
                    try:
                        # Wrap in root for parsing
                        xml_fragment = f'<?xml version="1.0" encoding="UTF-8"?><ENVELOPE>{vb}</ENVELOPE>'
                        d = xmltodict.parse(xml_fragment)
                        # Extract voucher dict
                        v = d.get('ENVELOPE', {}).get('VOUCHER')
                        if v:
                            vouchers.append(v)
                            recovered += 1
                        else:
                            skipped += 1
                    except Exception as ve:
                        skipped += 1
                log(f"[RECOVERY] Extracted {recovered} vouchers from malformed XML, skipped {skipped}.")
                # Save failed chunk for manual review
                try:
                    with open("failed_chunk_raw.xml", "w", encoding="utf-8") as f:
                        f.write(response.text)
                except Exception as file_err:
                    log(f"File write error (failed_chunk_raw.xml): {file_err}")
                # Return as if it was a normal response
                return {'ENVELOPE': {'VOUCHER': vouchers}}
        else:
            log(f"❌ HTTP error: {response.status_code}")
            log(f"Response: {response.text[:200]}...")
            return None
    except Exception as e:
        log(f"❌ Request error: {e}")
        raise

# --- Enhanced company name detection logic from test_enhanced_connector.py ---
def print_available_companies():
    """Print all available company names from Tally for debugging."""
    xml_request = '''
    <ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>List of Companies</REPORTNAME>
                    <STATICVARIABLES>
                        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>
    '''
    try:
        response = requests.post("http://localhost:9000", data=xml_request)
        cleaned = sanitize_xml(response.text)
        root = ET.fromstring(cleaned)
        companies = []
        for company in root.findall(".//COMPANY"):
            name_element = company.find("NAME")
            if name_element is not None and name_element.text:
                companies.append(name_element.text.strip())
        print("\nAvailable companies in Tally:")
        for cname in companies:
            print(f"- {cname}")
        if not companies:
            print("No companies found. Check Tally or XML response.")
    except Exception as e:
        print(f"Error fetching company list: {e}")


def get_company_name():
    """Try multiple methods to automatically detect company name from Tally."""
    def get_company_name_method1():
        xml_request = '''
        <ENVELOPE>
            <HEADER>
                <TALLYREQUEST>Export Data</TALLYREQUEST>
            </HEADER>
            <BODY>
                <EXPORTDATA>
                    <REQUESTDESC>
                        <REPORTNAME>List of Companies</REPORTNAME>
                        <STATICVARIABLES>
                            <SVEXPORTFORMAT>$SysName:XML</SVEXPORTFORMAT>
                        </STATICVARIABLES>
                    </REQUESTDESC>
                </EXPORTDATA>
            </BODY>
        </ENVELOPE>
        '''
        try:
            response = requests.post("http://localhost:9000", data=xml_request)
            cleaned = sanitize_xml(response.text)
            root = ET.fromstring(cleaned)
            company_paths = [
                ".//NAME",
                ".//COMPANYNAME",
                ".//COMPANY/NAME",
                ".//TALLYMESSAGE/COMPANY/NAME"
            ]
            for path in company_paths:
                name_element = root.find(path)
                if name_element is not None and name_element.text:
                    return name_element.text.strip()
        except Exception:
            pass
        return None

    def get_company_name_method2():
        xml_request = '''
        <ENVELOPE>
            <HEADER>
                <TALLYREQUEST>Export Data</TALLYREQUEST>
            </HEADER>
            <BODY>
                <EXPORTDATA>
                    <REQUESTDESC>
                        <REPORTNAME>List of Companies</REPORTNAME>
                        <STATICVARIABLES>
                            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                        </STATICVARIABLES>
                    </REQUESTDESC>
                </EXPORTDATA>
            </BODY>
        </ENVELOPE>
        '''
        try:
            response = requests.post("http://localhost:9000", data=xml_request)
            cleaned = sanitize_xml(response.text)
            root = ET.fromstring(cleaned)
            companies = []
            for company in root.findall(".//COMPANY"):
                name_element = company.find("NAME")
                if name_element is not None and name_element.text:
                    companies.append(name_element.text.strip())
            if companies:
                return companies[0]
        except Exception:
            pass
        return None

    def get_company_name_method3():
        xml_request = '''
        <ENVELOPE>
            <HEADER>
                <TALLYREQUEST>Export Data</TALLYREQUEST>
            </HEADER>
            <BODY>
                <EXPORTDATA>
                    <REQUESTDESC>
                        <REPORTNAME>Collection</REPORTNAME>
                        <STATICVARIABLES>
                            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                            <COLLECTIONNAME>Companies</COLLECTIONNAME>
                        </STATICVARIABLES>
                    </REQUESTDESC>
                </EXPORTDATA>
            </BODY>
        </ENVELOPE>
        '''
        try:
            response = requests.post("http://localhost:9000", data=xml_request)
            cleaned = sanitize_xml(response.text)
            root = ET.fromstring(cleaned)
            name_element = root.find(".//NAME")
            if name_element is not None and name_element.text:
                return name_element.text.strip()
        except Exception:
            pass
        return None

    def get_company_name_method4():
        xml_request = '''
        <ENVELOPE>
            <HEADER>
                <TALLYREQUEST>Export Data</TALLYREQUEST>
            </HEADER>
            <BODY>
                <EXPORTDATA>
                    <REQUESTDESC>
                        <REPORTNAME>Day Book</REPORTNAME>
                        <STATICVARIABLES>
                            <SVEXPORTFORMAT>$SysName:XML</SVEXPORTFORMAT>
                            <SVFROMDATE>01-04-2024</SVFROMDATE>
                            <SVTODATE>01-04-2024</SVTODATE>
                        </STATICVARIABLES>
                    </REQUESTDESC>
                </EXPORTDATA>
            </BODY>
        </ENVELOPE>
        '''
        try:
            response = requests.post("http://localhost:9000", data=xml_request)
            if "COMPANYNAME" in response.text:
                match = re.search(r'COMPANYNAME[>="\s]*([^<>"]*)', response.text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            cleaned = sanitize_xml(response.text)
            root = ET.fromstring(cleaned)
            company_elements = root.findall(".//COMPANYNAME")
            if company_elements:
                for elem in company_elements:
                    if elem.text and elem.text.strip():
                        return elem.text.strip()
            envelope = root.find("ENVELOPE")
            if envelope is not None:
                for attr_name, attr_value in envelope.attrib.items():
                    if 'COMPANY' in attr_name.upper() and attr_value:
                        return attr_value.strip()
        except Exception:
            pass
        return None

    def get_company_name_method5():
        xml_request = '''
        <ENVELOPE>
            <HEADER>
                <TALLYREQUEST>Export Data</TALLYREQUEST>
            </HEADER>
            <BODY>
                <EXPORTDATA>
                    <REQUESTDESC>
                        <REPORTNAME>Trial Balance</REPORTNAME>
                        <STATICVARIABLES>
                            <SVEXPORTFORMAT>$SysName:XML</SVEXPORTFORMAT>
                            <SVFROMDATE>01-04-2024</SVFROMDATE>
                            <SVTODATE>31-03-2025</SVTODATE>
                        </STATICVARIABLES>
                    </REQUESTDESC>
                </EXPORTDATA>
            </BODY>
        </ENVELOPE>
        '''
        try:
            response = requests.post("http://localhost:9000", data=xml_request)
            cleaned = sanitize_xml(response.text)
            root = ET.fromstring(cleaned)
            possible_tags = ['COMPANYNAME', 'TITLE', 'HEADER', 'NAME']
            for tag in possible_tags:
                elements = root.findall(f".//{tag}")
                for elem in elements:
                    if elem.text and len(elem.text.strip()) > 5:
                        potential_name = elem.text.strip()
                        if any(indicator in potential_name.lower() for indicator in ['ltd', 'pvt', 'limited', 'company', 'corp']):
                            return potential_name
        except Exception:
            pass
        return None

    methods = [
        get_company_name_method1,
        get_company_name_method2,
        get_company_name_method3,
        get_company_name_method4,
        get_company_name_method5
    ]
    for method in methods:
        try:
            company_name = method()
            if company_name and company_name.strip():
                return company_name.strip()
        except Exception:
            continue
    return None

def extract_vouchers_from_response(response_data):
    """Extract vouchers from any nested structure in Tally response."""
    vouchers = []
    
    def traverse_and_extract(obj):
        if isinstance(obj, dict):
            # Check if this object contains vouchers
            if 'VOUCHER' in obj:
                voucher_data = obj['VOUCHER']
                if isinstance(voucher_data, list):
                    for v in voucher_data:
                        if isinstance(v, dict) and any(key in v for key in ['VOUCHERNUMBER', 'DATE', 'VOUCHERTYPENAME']):
                            # Filter out null system lists
                            v = {k: v for k, v in v.items() if not (k.endswith('.LIST') and v is None)}
                            vouchers.append(v)
                elif isinstance(voucher_data, dict) and any(key in voucher_data for key in ['VOUCHERNUMBER', 'DATE', 'VOUCHERTYPENAME']):
                    # Filter out null system lists
                    voucher_data = {k: v for k, v in voucher_data.items() if not (k.endswith('.LIST') and v is None)}
                    vouchers.append(voucher_data)
            
            # Recursively check all values
            for key, value in obj.items():
                if isinstance(value, (dict, list)) and not key.endswith('.LIST'):
                    traverse_and_extract(value)
        elif isinstance(obj, list):
            for item in obj:
                traverse_and_extract(item)
    
    traverse_and_extract(response_data)
    return vouchers

def fetch_all_vouchers_by_daybook(start_date, end_date):
    """Fetch ALL vouchers using Day Book method - most reliable for getting complete data."""
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
    
    log(f"Fetching all vouchers from Day Book: {start_date} to {end_date}")
    result = send_tally_request(xml_request)
    
    if not result:
        log("❌ No response from Tally Day Book")
        return []
    
    # Extract all vouchers from the response
    all_vouchers = extract_vouchers_from_response(result)
    
    # Log voucher types found
    voucher_types = {}
    for voucher in all_vouchers:
        if isinstance(voucher, dict):
            vtype = voucher.get('VOUCHERTYPENAME', 'Unknown').strip()
            voucher_types[vtype] = voucher_types.get(vtype, 0) + 1
    
    log(f"✅ Day Book extracted {len(all_vouchers)} vouchers")
    log(f"Voucher types found: {voucher_types}")
    
    return all_vouchers

def fetch_vouchers_by_type(report_name, start_date, end_date):
    """
    Fetch vouchers of a specific type using the correct Tally report name (e.g., 'Sales Vouchers').
    Returns a list of voucher dicts.
    """
    xml_request = f"""
    <ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>{report_name}</REPORTNAME>
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
    log(f"Fetching vouchers from report '{report_name}' for {start_date} to {end_date}")
    result = send_tally_request(xml_request)
    if not result:
        log(f"❌ No response from Tally for {report_name}")
        return []
    vouchers = extract_vouchers_from_response(result)
    log(f"✅ Extracted {len(vouchers)} vouchers from {report_name}")
    return vouchers

def fetch_vouchers_by_type_chunked(report_name, start_date, end_date, chunk_days=1):
    """
    Fetch vouchers of a specific type in chunks to avoid Tally timeouts.
    Returns a list of voucher dicts.
    """
    start = parser.parse(start_date)
    end = parser.parse(end_date)
    all_vouchers = []
    chunk_count = 0
    while start <= end:
        chunk_start = start
        chunk_end = min(start + timedelta(days=chunk_days-1), end)
        chunk_start_str = chunk_start.strftime('%Y%m%d')
        chunk_end_str = chunk_end.strftime('%Y%m%d')
        log(f"Fetching {report_name} chunk: {chunk_start_str} to {chunk_end_str}")
        vouchers = fetch_vouchers_by_type(report_name, chunk_start_str, chunk_end_str)
        all_vouchers.extend(vouchers)
        log(f"Chunk {chunk_start_str}-{chunk_end_str}: {len(vouchers)} vouchers")
        start = chunk_end + timedelta(days=1)
        chunk_count += 1
    log(f"✅ Total {report_name} vouchers fetched in chunks: {len(all_vouchers)}")
    return all_vouchers

def fetch_all_7_voucher_types(start_date, end_date, chunk_days=1):
    """
    Fetch all 7 accounting voucher types using the correct report names, in chunks.
    Returns a list of all vouchers (dicts) for the date range.
    """
    report_map = [
        ("Sales Vouchers", "Sales"),
        ("Purchase Vouchers", "Purchase"),
        ("Payment Vouchers", "Payment"),
        ("Receipt Vouchers", "Receipt"),
        ("Journal Vouchers", "Journal"),
        ("Credit Note Vouchers", "Credit Note"),
        ("Debit Note Vouchers", "Debit Note"),
    ]
    all_vouchers = []
    type_counts = {}
    for report_name, vtype in report_map:
        vouchers = fetch_vouchers_by_type_chunked(report_name, start_date, end_date, chunk_days=chunk_days)
        for voucher in vouchers:
            if isinstance(voucher, dict):
                voucher_type = voucher.get('VOUCHERTYPENAME', '').strip()
                type_counts[voucher_type] = type_counts.get(voucher_type, 0) + 1
                all_vouchers.append(voucher)
        log(f"{report_name}: {len(vouchers)} vouchers fetched.")
    log(f"✅ Total vouchers extracted: {len(all_vouchers)} by type: {type_counts}")
    return all_vouchers

def fetch_accounting_vouchers_only(start_date, end_date, chunk_days=1):
    """
    Fetch only the 7 accounting voucher types using the correct report names, in chunks.
    Returns a list of voucher dicts.
    """
    return fetch_all_7_voucher_types(start_date, end_date, chunk_days=chunk_days)

def get_party_from_voucher(voucher, ledger_entries=None):
    """
    Extract party name from a voucher using multiple detection methods and type information.
    
    Args:
        voucher (dict): The voucher dictionary from Tally
        ledger_entries (list, optional): Pre-extracted ledger entries if available
        
    Returns:
        tuple: (party_name, party_type) where party_type is one of: 'customer', 'vendor', 'other'
    """
    # Ensure voucher is a dictionary
    if not isinstance(voucher, dict):
        return 'Unknown Party', 'other'

    # First get ledger entries if not provided
    if not ledger_entries:
        try:
            ledger_entries = extract_ledger_entries_from_voucher(voucher) or []
        except Exception as e:
            log(f"Error extracting ledger entries: {str(e)}")
            ledger_entries = []
    
    # Method 1: Direct PARTYNAME field with enhanced safety
    try:
        party_name = str(voucher.get('PARTYNAME', '') or '').strip()
        if party_name:
            # Try to determine type from voucher fields
            voucher_type = str(voucher.get('VOUCHERTYPENAME', '') or '').upper()
            if voucher_type in ['SALES', 'RECEIPT']:
                return party_name, 'customer'
            elif voucher_type in ['PURCHASE', 'PAYMENT']:
                return party_name, 'vendor'
    except (AttributeError, TypeError) as e:
        log(f"Error processing PARTYNAME: {str(e)}")
        party_name = ''
    
    # Method 2: Check PARTYLEDGERNAME with enhanced safety
    try:
        party_name = str(voucher.get('PARTYLEDGERNAME', '') or '').strip()
        if party_name:
            # Look for the party in ledger entries to determine type
            for entry in (ledger_entries or []):
                if not isinstance(entry, dict):
                    continue
                
                entry_name = str(entry.get('ledger_name', '') or '').strip()
                if entry_name == party_name:
                    entry_type = str(entry.get('type', '') or '').strip()
                    entry_group = str(entry.get('group', '') or '').strip().lower()
                    
                    if entry_type == 'Asset' and 'debtor' in entry_group:
                        return party_name, 'customer'
                    elif entry_type == 'Liability' and 'creditor' in entry_group:
                        return party_name, 'vendor'
                    return party_name, 'other'
    except (AttributeError, TypeError) as e:
        log(f"Error processing PARTYLEDGERNAME: {str(e)}")
        party_name = ''
    
    # Method 3: Analyze ledger entries
    for entry in ledger_entries:
        ledger_name = entry.get('ledger_name', '').strip()
        ledger_type = entry.get('type')
        ledger_group = entry.get('group', '').lower()
        
        # Normalize ledger group for better matching
        ledger_group = ' '.join(word.lower().strip() for word in ledger_group.replace('-', ' ').split())
        
        # Skip common non-party ledgers
        if any(word in ledger_name.lower() for word in 
               ['cash', 'bank', 'gst', 'tax', 'tds', 'expenses', 'income', 'profit', 'loss']):
            continue
            
        # Direct checks for sundry debtors/creditors
        if ('sundry debtor' in ledger_group or 'debtor' in ledger_group or 
            'receivable' in ledger_group or 'sundry debtors' in ledger_group):
            return ledger_name, 'customer'
            
        if ('sundry creditor' in ledger_group or 'creditor' in ledger_group or
            'payable' in ledger_group or 'sundry creditors' in ledger_group):
            return ledger_name, 'vendor'
            
        # Check if this looks like a business name
        if any(indicator.lower() in ledger_name.lower() for indicator in 
               ['ltd', 'limited', 'pvt', 'private', 'llp', 'corporation', 'inc',
                'company', 'enterprises', 'industries', 'solutions', 'technologies',
                'trading', 'traders']):
            # Use ledger type/group to determine party type
            if ledger_type == 'Asset' and ('debtor' in ledger_group or 'receivable' in ledger_group):
                return ledger_name, 'customer'
            elif ledger_type == 'Liability' and ('creditor' in ledger_group or 'payable' in ledger_group):
                return ledger_name, 'vendor'
            return ledger_name, 'other'
            
        # Check for sundry debtors/creditors groups
        if ledger_type in ['Asset', 'Liability'] and any(term in ledger_group for term in ['debtor', 'creditor', 'receivable', 'payable']):
            party_type = 'customer' if any(term in ledger_group for term in ['debtor', 'receivable']) else 'vendor'
            return ledger_name, party_type
    
    # Method 4: Look for reference field hints
    ref_fields = ['REFERENCE', 'BILLREF', 'PERSISTEDVIEW']
    for field in ref_fields:
        if field in voucher:
            value = str(voucher[field]).strip().lower()
            if any(word in value for word in ['bill', 'invoice']):
                return value.split(':')[-1].strip() or 'Unknown', 'customer'
            elif any(word in value for word in ['po', 'purchase', 'order']):
                return value.split(':')[-1].strip() or 'Unknown', 'vendor'
            
            # Check for common naming patterns
            patterns = [
                r'(?:party|client)[:\s]+([^\d\n]+)',  # General party/client
                r'(?:vendor|supplier)[:\s]+([^\d\n]+)',  # Vendor specific
                r'(?:customer|buyer)[:\s]+([^\d\n]+)',  # Customer specific
                r'(?:bill to|ship to)[:\s]+([^\d\n]+)',  # Shipping details
                r'(?:M/s\.?|Messrs\.?)\s+([^\d\n]+)'  # Business prefix
            ]
            for pattern in patterns:
                match = re.search(pattern, value, re.IGNORECASE)
                if match:
                    party_name = match.group(1).strip()
                    if 'vendor' in pattern or 'supplier' in pattern:
                        return party_name, 'vendor'
                    elif 'customer' in pattern or 'buyer' in pattern:
                        return party_name, 'customer'
                    return party_name, 'other'
                    
    # If all methods fail, return Unknown
    return "Unknown", 'other'

def map_group_to_ledger_type(group):
    """Map Tally group to standardized ledger type."""
    group = group.strip().lower()
    if group in [
        "bank accounts", "sundry debtors", "cash-in-hand", "loans & advances (asset)",
        "fixed assets", "current assets", "deposits (asset)", "stock-in-hand", "investments"
    ]:
        return "Asset"
    elif group in ["capital account", "reserves & surplus", "profit & loss a/c"]:
        return "Capital"
    elif group in ["sales accounts", "direct incomes", "indirect incomes", "commission received", "interest received"]:
        return "Income"
    elif group in [
        "purchase accounts", "direct expenses", "indirect expenses", "administrative expenses",
        "selling & distribution expenses", "cost of sales", "salary & wages", "freight inward", "interest paid"
    ]:
        return "Expense"
    elif group in [
        "sundry creditors", "loans (liability)", "secured loans", "unsecured loans",
        "duties & taxes", "provisions", "current liabilities", "bank od a/c", "suspense a/c"
    ]:
        return "Liability"
    return "Unknown"

def extract_ledger_entries_from_voucher(voucher):
    """
    Extract all credit/debit ledger entries from a voucher dict with enhanced type detection.
    Returns a list of dicts: [{ledger_name, amount, is_debit, is_credit, type, group, ...}]
    """
    entries = []
    # Tally can use ALLLEDGERENTRIES.LIST or LEDGERENTRIES.LIST
    ledger_lists = []
    for key in ["ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST"]:
        if key in voucher:
            val = voucher[key]
            if isinstance(val, list):
                ledger_lists.extend(val)
            elif isinstance(val, dict):
                ledger_lists.append(val)
    for entry in ledger_lists:
        if not isinstance(entry, dict):
            continue
            
        # Extract basic ledger info
        ledger_name = entry.get("LEDGERNAME", "").strip()
        if not ledger_name:
            # Try alternate name fields
            for name_field in ["NAME", "LANGUAGENAME.LIST/NAME.LIST/NAME"]:
                if entry.get(name_field):
                    ledger_name = entry[name_field].strip()
                    break
        
        # Get group/parent info
        group = None
        for group_field in ["PARENT", "GROUP", "PARENTTYPE"]:
            if entry.get(group_field):
                group = entry[group_field].strip()
                break
        if not group:
            group = "[NO GROUP]"
            
        # Determine ledger type
        ledger_type = map_group_to_ledger_type(group)
        
        # Process amount
        amount = entry.get("AMOUNT", "0")
        try:
            amt_val = float(str(amount).replace(",", ""))
        except:
            amt_val = 0.0
            
        # Determine debit/credit status
        is_debit = amt_val > 0 or entry.get("ISDEBIT", "").upper() == "YES"
        is_credit = amt_val < 0 or entry.get("ISCREDIT", "").upper() == "YES"
        
        # Build enhanced entry object
        entries.append({
            "ledger_name": ledger_name,
            "amount": amt_val,
            "is_debit": is_debit,
            "is_credit": is_credit,
            "type": ledger_type,
            "group": group,
            "raw_amount": amount,
            "all_fields": entry
        })
    return entries

def fetch_ledger_opening_balances(company_name=None, max_retries=3):
    """Fetch opening balances for all ledgers for a specific company with enhanced retry logic.
    
    Args:
        company_name (str, optional): The name of the company to fetch data for. 
            If None, will attempt to auto-detect.
        max_retries (int, optional): Maximum number of retry attempts for failed requests.
            Defaults to 3.
            
    Returns:
        list: List of dictionaries containing ledger opening balances.
    """
    if not company_name:
        company_name = get_company_name()
        if not company_name:
            log("❌ Failed to detect company name", level="ERROR")
            return []
            
    xml_request = f'''
<ENVELOPE>
    <HEADER>
        <TALLYREQUEST>Export Data</TALLYREQUEST>
    </HEADER>
    <BODY>
        <EXPORTDATA>
            <REQUESTDESC>
                <REPORTNAME>List of Accounts</REPORTNAME>
                <STATICVARIABLES>
                    <ACCOUNTTYPE>Ledger</ACCOUNTTYPE>
                    <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
                    <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    <SVFROMDATE>20220401</SVFROMDATE>
                    <SVTODATE>20220401</SVTODATE>
                </STATICVARIABLES>
            </REQUESTDESC>
        </EXPORTDATA>
    </BODY>
</ENVELOPE>
'''
    log(f"Fetching ledger opening balances for company: {company_name}")
    
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            session = create_session()
            response = session.post(
                TALLY_URL, 
                data=xml_request.encode('utf-8'),
                timeout=(CONNECTION_TIMEOUT, READ_TIMEOUT)
            )
            
            if response.status_code != 200:
                raise requests.exceptions.RequestException(
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
            
            # Save raw response for debugging
            try:
                with open("raw_tally_response.xml", "w", encoding="utf-8") as f:
                    f.write(response.text)
            except Exception as e:
                log(f"Warning: Could not save raw response: {e}", level="WARN")
            
            # Save a memory-safe copy and try to clean. If the response is very large
            # sanitize_xml may raise MemoryError; handle that by streaming LEDGER blocks
            opening_balances = []
            try:
                # Write raw response first (already attempted above) and then try to clean
                cleaned_text = sanitize_xml(response.text)
                if not cleaned_text.strip():
                    raise ValueError("Empty response from Tally")
                large_response = len(response.text) > (5 * 1024 * 1024)  # 5 MB threshold
                if large_response:
                    log(f"Warning: Large response detected ({len(response.text)} bytes). Using streaming parse.", level="WARN")
                # If cleaning succeeded, proceed normally
            except MemoryError as me:
                log(f"MemoryError while cleaning XML: {me}. Falling back to streaming extraction.", level="ERROR")
                # Ensure raw response file exists and stream parse ledger blocks from it
                try:
                    with open('raw_tally_response.xml', 'w', encoding='utf-8') as f:
                        f.write(response.text)
                except Exception as wf:
                    log(f"Could not write raw response for streaming parse: {wf}", level="ERROR")

                # Stream-extract LEDGER blocks from the file to avoid building a huge string in memory
                try:
                    in_block = False
                    buffer_lines = []
                    with open('raw_tally_response.xml', 'r', encoding='utf-8', errors='ignore') as rf:
                        for line in rf:
                            if '<LEDGER' in line and not in_block:
                                in_block = True
                                buffer_lines = [line]
                                continue
                            if in_block:
                                buffer_lines.append(line)
                                if '</LEDGER>' in line:
                                    ledger_xml = ''.join(buffer_lines)
                                    # parse this single ledger block safely
                                    try:
                                        parsed = xmltodict.parse('<?xml version="1.0" encoding="UTF-8"?><ENVELOPE>' + ledger_xml + '</ENVELOPE>')
                                        led = parsed.get('ENVELOPE', {}).get('LEDGER')
                                        if led:
                                            # map fields similar to normal flow
                                            name_tag = led.get('NAME')
                                            name = name_tag.strip() if isinstance(name_tag, str) and name_tag else None
                                            if not name and isinstance(led.get('LANGUAGENAME.LIST'), dict):
                                                ln = led['LANGUAGENAME.LIST'].get('NAME.LIST', {}).get('NAME')
                                                if isinstance(ln, str):
                                                    name = ln.strip()
                                            group = led.get('PARENT') or '[NO GROUP]'
                                            opening = led.get('OPENINGBALANCE') or '0'
                                            try:
                                                cleaned_balance = re.sub(r'[^\d.-]', '', str(opening))
                                                balance_value = float(cleaned_balance) if cleaned_balance else 0.0
                                            except:
                                                balance_value = 0.0
                                            if name and balance_value != 0:
                                                opening_balances.append({
                                                    'ledger_name': name,
                                                    'opening_balance': balance_value,
                                                    'group': group,
                                                    'raw_balance': opening
                                                })
                                    except Exception as pe:
                                        log(f"Streaming parse error for a ledger block: {pe}", level='WARN')
                                    in_block = False
                                    buffer_lines = []
                    # After streaming extraction, if we got ledgers, we're successful
                    if opening_balances:
                        log(f"✅ Stream-extracted {len(opening_balances)} ledger opening balances for company: {company_name}")
                        # Save results and return early
                        with open('opening_balances.json', 'w', encoding='utf-8') as f:
                            json.dump(opening_balances, f, indent=2, ensure_ascii=False)
                        return opening_balances
                except Exception as se:
                    log(f"Streaming extraction failed: {se}", level='ERROR')
                    # fallthrough to normal processing which will attempt cleanup again
            except Exception as e:
                # Other exceptions during cleaning - rethrow or fallback
                log(f"XML cleaning exception: {e}", level='ERROR')
                # fallthrough to default behavior
            
            # If we reach here and cleaned_text exists, proceed normally; otherwise continue and let later parsing handle empty
            try:
                if 'cleaned_text' not in locals():
                    cleaned_text = sanitize_xml(response.text)
                # continue normal flow
            except MemoryError:
                log("MemoryError on second sanitize attempt; aborting and returning empty list", level='ERROR')
                return []

            break  # Success, exit retry loop
            
        except (requests.exceptions.RequestException, 
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            last_error = e
            retry_count += 1
            if retry_count < max_retries:
                wait_time = min(RETRY_DELAY * (2 ** (retry_count - 1)), 30)
                log(f"Retrying in {wait_time}s... ({retry_count}/{max_retries})", level="WARN")
                time.sleep(wait_time)
            continue
            
        finally:
            try:
                session.close()
            except:
                pass
                
    if retry_count == max_retries:
        log(f"❌ Failed to fetch data after {max_retries} attempts: {last_error}", level="ERROR")
        return []
    
    try:
        root = ET.fromstring(cleaned_text)
        ledgers = root.findall(".//LEDGER")
        
        if not ledgers:
            log("⚠️ No LEDGER entries found. Check if company name is correct and data exists.")
            log("📋 Available companies might be different. Check Tally company list.")
        else:
            for ledger in ledgers:
                # Ledger Name
                name_tag = ledger.find("NAME")
                name = name_tag.text.strip() if name_tag is not None and name_tag.text else None
                
                if not name:
                    name_list = ledger.find(".//LANGUAGENAME.LIST/NAME.LIST/NAME")
                    if name_list is not None and name_list.text:
                        name = name_list.text.strip()
                if not name:
                    name = "[NO NAME]"
                
                # Group
                parent_tag = ledger.find("PARENT")
                group = parent_tag.text.strip() if parent_tag is not None and parent_tag.text else "[NO GROUP]"
                
                # Opening Balance
                opening_tag = ledger.find("OPENINGBALANCE")
                opening = opening_tag.text.strip() if opening_tag is not None and opening_tag.text else "0"
                
                # Clean and convert opening balance
                try:
                    cleaned_balance = re.sub(r'[^\d.-]', '', opening)
                    balance_value = float(cleaned_balance) if cleaned_balance else 0.0
                except:
                    balance_value = 0.0
                
                if name and balance_value != 0:
                    opening_balances.append({
                        'ledger_name': name,
                        'opening_balance': balance_value,
                        'group': group,
                        'raw_balance': opening
                    })
                    
        log(f"✅ Extracted {len(opening_balances)} ledger opening balances for company: {company_name}")
    except ET.ParseError as e:
        log(f"❌ XML Parse Error: {e}")
        log("🔍 Check 'raw_tally_response.xml' for issues.")
        log("💡 The company name might be incorrect or Tally might not be responding properly.")
        
    # Save results to file for debugging
    with open("opening_balances.json", "w", encoding="utf-8") as f:
        json.dump(opening_balances, f, indent=2, ensure_ascii=False)
        
    return opening_balances

# Recovery: also provide a function to convert recovered vouchers to transaction list

def recover_failed_chunk_transactions(xml_path="failed_chunk_raw.xml"):
    """Convert recovered vouchers from failed chunk XML into transaction dicts with all ledger entries."""
    vouchers = recover_failed_chunk_vouchers(xml_path)
    transactions = []
    for voucher in vouchers:
        if isinstance(voucher, dict):
            vtype = voucher.get('VOUCHERTYPENAME', '').strip()
            voucher_number = voucher.get('VOUCHERNUMBER', '')
            narration = voucher.get('NARRATION', '')
            date = voucher.get('DATE', '')
            ledger_entries = extract_ledger_entries_from_voucher(voucher)
            for entry in ledger_entries:
                txn = {
                    'voucher_type': vtype,
                    'register_type': vtype.lower().replace(' ', '_'),
                    'voucher_number': voucher_number,
                    'narration': narration,
                    'date': date,
                    'ledger_name': entry['ledger_name'],
                    'amount': entry['amount'],
                    'is_debit': entry['is_debit'],
                    'is_credit': entry['is_credit'],
                    'raw_amount': entry['raw_amount'],
                    'ledger_entry': entry['all_fields'],
                    'voucher_all_fields': voucher
                }
                transactions.append(txn)
    return transactions

def recover_failed_chunk_vouchers(xml_path="failed_chunk_raw.xml"):
    """
    Extract all <VOUCHER> blocks from a failed chunk XML file, parse each individually, and return as list of dicts.
    Handles malformed XML by extracting blocks with regex.
    """
    vouchers = []
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            raw_xml = f.read()
    except Exception as e:
        print(f"Failed to read {xml_path}: {e}")
        return []
    # Use regex to extract all <VOUCHER>...</VOUCHER> blocks
    voucher_blocks = re.findall(r'<VOUCHER[\s\S]*?</VOUCHER>', raw_xml, re.IGNORECASE)
    for block in voucher_blocks:
        try:
            # Wrap in a root for parsing
            xml_str = f'<ROOT>{block}</ROOT>'
            root = ET.fromstring(xml_str)
            voucher_elem = root.find('VOUCHER')
            if voucher_elem is not None:
                voucher_dict = {}
                for child in voucher_elem:
                    if list(child):
                        # Store subchildren as a list under a new key
                        voucher_dict[child.tag + '_LIST'] = [
                            {gchild.tag: gchild.text for gchild in subchild}
                            if list(subchild) else subchild.text
                            for subchild in child
                        ]
                    else:
                        voucher_dict[child.tag] = child.text
                vouchers.append(voucher_dict)
        except Exception as e:
            # Log and skip malformed block
            print(f"Failed to parse voucher block: {e}")
            continue
    return vouchers

# --- Export modes for data sync ---
def fetch_all_registers(start_date, end_date):
    """Enhanced function to fetch all 7 accounting voucher types, including all ledger entries."""
    accounting_vouchers = fetch_accounting_vouchers_only(start_date, end_date)
    transactions = []
    required_fields = ["party_name", "voucher_number", "voucher_type", "date", "amount", "ledger_entries"]
    skipped_vouchers = []

    for voucher in accounting_vouchers:
        if isinstance(voucher, dict):
            vtype = voucher.get('VOUCHERTYPENAME', '')
            voucher_number = voucher.get('VOUCHERNUMBER', '')
            narration = voucher.get('NARRATION', '')
            date = voucher.get('DATE', '')
            ledger_entries = extract_ledger_entries_from_voucher(voucher)
            
            # Enhanced party name detection with type
            party_info = get_party_from_voucher(voucher, ledger_entries)
            party_name, party_type = party_info if isinstance(party_info, tuple) else (party_info, 'unknown')
            
            # Get amount with fallbacks
            amount = voucher.get('AMOUNT', '')
            
            # Validate party name based on ledger groups and types
            if party_name == "Unknown":
                for entry in ledger_entries:
                    # Skip entries we know aren't parties
                    if any(word in entry.get('ledger_name', '').lower() for word in 
                          ['cash', 'bank', 'gst', 'tax', 'tds', 'expenses', 'income', 'profit', 'loss']):
                        continue
                        
                    ledger_group = entry.get('group', '').lower()
                    ledger_type = entry.get('type')
                    
                    # Check for sundry debtors/creditors and other party indicators
                    if any(term in ledger_group for term in ['sundry debtor', 'debtor', 'receivable']):
                        party_name = entry.get('ledger_name', '')
                        party_type = 'customer'
                        break
                    elif any(term in ledger_group for term in ['sundry creditor', 'creditor', 'payable']):
                        party_name = entry.get('ledger_name', '')
                        party_type = 'vendor'
                        break
                    # Secondary check for business name indicators
                    elif any(term in entry.get('ledger_name', '').lower() for term in 
                           ['ltd', 'limited', 'pvt', 'private', 'llp', 'corporation', 'inc',
                            'company', 'enterprises', 'industries', 'solutions', 'technologies']):
                        party_name = entry.get('ledger_name', '')
                        party_type = 'vendor' if ledger_type == 'Liability' else 'customer' if ledger_type == 'Asset' else 'other'
                        break

            # Enhanced party name detection
            if not party_name or party_name == "Unknown":
                # Try to find party name from ledger entries
                for entry in ledger_entries:
                    ledger_name = entry.get('ledger_name', '').strip()
                    # Check if this ledger is likely a party (common suffixes/patterns)
                    if any(indicator.lower() in ledger_name.lower() for indicator in 
                          ['ltd', 'limited', 'pvt', 'private', 'llp', 'corporation', 'inc', 
                           'trading', 'enterprises', 'industries', 'company']):
                        party_name = ledger_name
                        break
                    
            # If amount is empty, fallback to party ledger entry amount
            if (amount is None or str(amount).strip() == '') and ledger_entries:
                # Try to find the party ledger entry
                party_entry = None
                for entry in ledger_entries:
                    ledger_name_val = entry.get('ledger_name', '')
                    party_name_val = party_name or ''
                    if str(ledger_name_val).strip() == str(party_name_val).strip():
                        party_entry = entry
                        break
                
                if party_entry and 'amount' in party_entry:
                    amount = str(party_entry['amount'])
                elif ledger_entries:
                    # Fallback: use first ledger entry's amount
                    amount = str(ledger_entries[0]['amount'])

            # Create transaction dict with enhanced party information
            txn = {
                'voucher_type': vtype or '',
                'voucher_number': voucher_number or '',
                'date': date or '',
                'amount': amount or '',
                'party_name': party_name or '',
                'party_type': party_type,  # Include party type for better processing
                'ledger_entries': [
                    {
                        **entry,
                        'standardized_type': map_group_to_ledger_type(entry.get('group', ''))
                    } for entry in ledger_entries
                ],
                'narration': narration,
                'voucher_all_fields': voucher
            }

            # Check for required fields
            missing_fields = [
                field for field in required_fields 
                if field not in txn or not txn[field]
            ]

            # Handle missing fields
            if missing_fields:
                txn['missing_fields'] = missing_fields
                skipped_vouchers.append(txn)
            else:
                transactions.append(txn)

    # Log skipped vouchers for review
    if skipped_vouchers:
        try:
            with open("skipped_vouchers.json", "w", encoding="utf-8") as f:
                json.dump(skipped_vouchers, f, indent=2, ensure_ascii=False)
            log(f"[FILTER] Skipped {len(skipped_vouchers)} vouchers missing critical fields. See skipped_vouchers.json.", level="WARN")
        except Exception as e:
            log(f"[FILTER] Failed to write skipped vouchers: {e}", level="ERROR")

    return transactions

def export_complete_data(start_date, end_date):
    """Return both vouchers and opening balances."""
    vouchers = fetch_all_registers(start_date, end_date)
    opening_balances = fetch_ledger_opening_balances()
    return {
        "company_name": get_company_name(),
        "date_range": {"from_date": start_date, "to_date": end_date},
        "accounting_vouchers": vouchers,
        "opening_balances": opening_balances
    }

def export_vouchers_only(start_date, end_date):
    """Return only vouchers."""
    vouchers = fetch_all_registers(start_date, end_date)
    return {
        "company_name": get_company_name(),
        "date_range": {"from_date": start_date, "to_date": end_date},
        "accounting_vouchers": vouchers
    }

def validate_api_connection(api_url, timeout=5):
    """Validate API connection before attempting data transfer.
    
    Args:
        api_url (str): The base URL of the API
        timeout (int): Connection timeout in seconds
        
    Returns:
        bool: True if API is reachable, False otherwise
    """
    try:
        # Try a HEAD request first to minimize data transfer
        response = requests.head(api_url, timeout=timeout)
        
        # If HEAD not allowed, fall back to GET
        if response.status_code in (405, 501, 404):
            response = requests.get(api_url, timeout=timeout)
            
        return response.status_code < 500
        
    except requests.exceptions.RequestException as e:
        log(f"❌ API connection check failed: {e}", level="ERROR")
        return False
        
def export_opening_balances_only(company_name=None):
    """Return only opening balances for the specified company name with enhanced validation."""
    # Validate company name
    if not company_name:
        company_name = get_company_name()
        if not company_name:
            log("❌ Could not determine company name", level="ERROR")
            return None
            
    # Fetch data with retries
    opening_balances = fetch_ledger_opening_balances(company_name, max_retries=3)
    if not opening_balances:
        log("❌ No opening balances retrieved", level="ERROR")
        return None
        
    return {
        "company_name": company_name,
        "opening_balances": opening_balances
    }

# CLI test runner
if __name__ == "__main__":
    print_available_companies()
    def test_connection():
        print("=" * 60)
        print("TESTING TALLY CONNECTION")
        print("=" * 60)
        return test_tally_connection()

    def test_company():
        print("\n" + "=" * 60)
        print("TESTING COMPANY NAME")
        print("=" * 60)
        company_name = get_company_name()
        if company_name:
            print(f"✅ Company: {company_name}")
            return True
        else:
            print("❌ Could not fetch company name")
            return False

    def test_vouchers():
        print("\n" + "=" * 60)
        print("TESTING VOUCHER EXTRACTION")
        print("=" * 60)
        vouchers = fetch_accounting_vouchers_only("20240401", "20240410")
        if vouchers:
            print(f"✅ Found {len(vouchers)} accounting vouchers")
            return True
        else:
            print("❌ No vouchers found")
            return False

    def test_opening_balances():
        print("\n" + "=" * 60)
        print("TESTING OPENING BALANCES")
        print("=" * 60)
        balances = fetch_ledger_opening_balances()
        if balances:
            print(f"✅ Found {len(balances)} opening balances")
            return True
        else:
            print("❌ No opening balances found")
            return False

    def test_complete_data():
        print("\n" + "=" * 60)
        print("TESTING COMPLETE DATA EXTRACTION")
        print("=" * 60)
        print("❌ Complete data extraction test is not implemented.")
        return False

    def main():
        print("🚀 ENHANCED TALLY CONNECTOR TESTS")
        print("=" * 60)
        
        tests = [
            ("Connection Test", test_connection),
            ("Company Name", test_company),
            ("Voucher Extraction", test_vouchers),
            ("Opening Balances", test_opening_balances),
            ("Complete Data", test_complete_data)
        ]
        
        results = {}
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
            except Exception as e:
                print(f"❌ {test_name} failed: {e}")
                results[test_name] = False
        
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        for test_name, result in results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name:20} : {status}")
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        print(f"\nOverall: {passed}/{total} tests passed")
        
        return passed == total

    success = main()
    sys.exit(0 if success else 1)


    