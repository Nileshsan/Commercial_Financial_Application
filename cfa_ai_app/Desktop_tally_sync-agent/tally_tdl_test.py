#!/usr/bin/env python3
"""
TDL Testing Script for Tally Integration
This script helps test the Export Data XML functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tally_connector import (
    test_tally_connection,
    fetch_export_data,
    fetch_export_data_json,
    get_company_name,
    log
)

def test_basic_connection():
    """Test basic connection to Tally"""
    print("=" * 60)
    print("TESTING BASIC TALLY CONNECTION")
    print("=" * 60)
    
    result = test_tally_connection()
    if result:
        print("✅ Basic connection to Tally successful!")
        return True
    else:
        print("❌ Basic connection to Tally failed!")
        return False

def test_company_info():
    """Test fetching company information"""
    print("\n" + "=" * 60)
    print("TESTING COMPANY INFO FETCH")
    print("=" * 60)
    
    try:
        company_name = get_company_name()
        if company_name:
            print(f"✅ Company Name: {company_name}")
            return True
        else:
            print("❌ Could not fetch company name")
            return False
    except Exception as e:
        print(f"❌ Error fetching company info: {e}")
        return False

def test_export_data_xml():
    """Test the Export Data XML TDL functionality"""
    print("\n" + "=" * 60)
    print("TESTING EXPORT DATA XML (TDL)")
    print("=" * 60)
    
    try:
        # Test with a small date range first
        start_date = "20240401"
        end_date = "20240430"
        
        print(f"Testing with date range: {start_date} to {end_date}")
        
        data = fetch_export_data(start_date, end_date)
        
        if data:
            print("✅ Export Data XML successful!")
            
            # Try to analyze the structure
            print("\n📊 DATA STRUCTURE ANALYSIS:")
            print("-" * 30)
            
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict):
                        print(f"📁 {key}: {len(value)} sub-elements")
                        for sub_key in list(value.keys())[:5]:  # Show first 5 keys
                            print(f"   └── {sub_key}")
                        if len(value) > 5:
                            print(f"   └── ... and {len(value) - 5} more")
                    elif isinstance(value, list):
                        print(f"📄 {key}: {len(value)} items")
                    else:
                        print(f"📝 {key}: {str(value)[:50]}...")
            
            return True
        else:
            print("❌ Export Data XML failed - no data returned")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Export Data XML: {e}")
        return False

def test_export_data_json():
    """Test the Export Data XML with JSON conversion"""
    print("\n" + "=" * 60)
    print("TESTING EXPORT DATA XML (JSON CONVERSION)")
    print("=" * 60)
    
    try:
        # Test with a small date range first
        start_date = "20240401"
        end_date = "20240430"
        
        print(f"Testing JSON conversion with date range: {start_date} to {end_date}")
        
        data = fetch_export_data_json(start_date, end_date)
        
        if data:
            print("✅ Export Data XML to JSON successful!")
            
            # Try to analyze the JSON structure
            print("\n📊 JSON STRUCTURE ANALYSIS:")
            print("-" * 30)
            
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict):
                        print(f"📁 {key}: {len(value)} sub-elements")
                    elif isinstance(value, list):
                        print(f"📄 {key}: {len(value)} items")
                    else:
                        print(f"📝 {key}: {str(value)[:50]}...")
            
            return True
        else:
            print("❌ Export Data XML to JSON failed - no data returned")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Export Data XML to JSON: {e}")
        return False

def main():
    """Main testing function"""
    print("🚀 STARTING TALLY TDL TESTING")
    print("=" * 60)
    
    # Test results
    tests = [
        ("Basic Connection", test_basic_connection),
        ("Company Info", test_company_info),
        ("Export Data XML", test_export_data_xml),
        ("Export Data JSON", test_export_data_json)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:25} : {status}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your TDL integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
