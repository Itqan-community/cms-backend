#!/usr/bin/env python3
"""
Test script to verify authentication separation between mock API and real API
"""
import json
import requests
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:8000"
MOCK_API_BASE = f"{BASE_URL}/mock-api"
REAL_API_BASE = f"{BASE_URL}/api/v1"

# Test credentials
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test"

def print_test_header(test_name):
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

def print_result(success, message):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {message}")

def test_mock_api_login():
    """Test mock API login and get mock token"""
    print_test_header("Mock API Login")
    
    try:
        response = requests.post(
            f"{MOCK_API_BASE}/auth/login/",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            mock_token = data.get("access_token")
            print_result(True, f"Mock login successful, got token: {mock_token[:50]}...")
            return mock_token
        else:
            print_result(False, f"Mock login failed: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Mock login request failed: {e}")
        return None

def test_real_api_login():
    """Test real API login and get real token"""
    print_test_header("Real API Login")
    
    try:
        response = requests.post(
            f"{REAL_API_BASE}/auth/login/",
            json={"email": "dev@localhost", "password": "dev123"},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            real_token = data.get("access_token")
            print_result(True, f"Real login successful, got token: {real_token[:50]}...")
            return real_token
        else:
            print_result(False, f"Real login failed: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Real login request failed: {e}")
        return None

def test_mock_token_with_mock_api(mock_token):
    """Test that mock token works with mock API authenticated endpoints"""
    print_test_header("Mock Token with Mock API")
    
    if not mock_token:
        print_result(False, "No mock token available")
        return False
    
    try:
        # Test authenticated mock endpoint
        response = requests.post(
            f"{MOCK_API_BASE}/assets/1/request-access/",
            json={"purpose": "Testing"},
            headers={
                "Authorization": f"Bearer {mock_token}",
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code in [200, 201]:
            print_result(True, "Mock token successfully authenticated with mock API")
            return True
        else:
            print_result(False, f"Mock token failed with mock API: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Mock token test request failed: {e}")
        return False

def test_real_token_with_real_api(real_token):
    """Test that real token works with real API endpoints"""
    print_test_header("Real Token with Real API")
    
    if not real_token:
        print_result(False, "No real token available")
        return False
    
    try:
        # Test authenticated real API endpoint
        response = requests.get(
            f"{REAL_API_BASE}/auth/profile/",
            headers={
                "Authorization": f"Bearer {real_token}",
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code == 200:
            print_result(True, "Real token successfully authenticated with real API")
            return True
        else:
            print_result(False, f"Real token failed with real API: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Real token test request failed: {e}")
        return False

def test_mock_token_with_real_api(mock_token):
    """Test that mock token is rejected by real API"""
    print_test_header("Mock Token with Real API (Should Fail)")
    
    if not mock_token:
        print_result(False, "No mock token available")
        return False
    
    try:
        response = requests.get(
            f"{REAL_API_BASE}/auth/profile/",
            headers={
                "Authorization": f"Bearer {mock_token}",
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code == 401:
            print_result(True, "Mock token correctly rejected by real API (401 Unauthorized)")
            return True
        else:
            print_result(False, f"Mock token should be rejected by real API but got: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Mock token rejection test failed: {e}")
        return False

def test_real_token_with_mock_api(real_token):
    """Test that real token is handled properly by mock API"""
    print_test_header("Real Token with Mock API")
    
    if not real_token:
        print_result(False, "No real token available")
        return False
    
    try:
        # Test authenticated mock endpoint with real token
        response = requests.post(
            f"{MOCK_API_BASE}/assets/1/request-access/",
            json={"purpose": "Testing"},
            headers={
                "Authorization": f"Bearer {real_token}",
                "Content-Type": "application/json"
            }
        )
        
        # Mock API should either accept it (if AllowAny) or reject it gracefully
        if response.status_code in [200, 201, 401, 403]:
            print_result(True, f"Real token handled properly by mock API: {response.status_code}")
            return True
        else:
            print_result(False, f"Real token caused unexpected response from mock API: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Real token with mock API test failed: {e}")
        return False

def main():
    """Run all authentication tests"""
    print(f"Authentication Separation Test Suite")
    print(f"Started at: {datetime.now()}")
    print(f"Testing against: {BASE_URL}")
    
    # Test individual authentication systems
    mock_token = test_mock_api_login()
    real_token = test_real_api_login()
    
    # Test token usage within same systems
    mock_api_success = test_mock_token_with_mock_api(mock_token)
    real_api_success = test_real_token_with_real_api(real_token)
    
    # Test cross-system rejection
    mock_rejected = test_mock_token_with_real_api(mock_token)
    real_handled = test_real_token_with_mock_api(real_token)
    
    # Summary
    print_test_header("TEST SUMMARY")
    
    total_tests = 6
    passed_tests = sum([
        bool(mock_token),
        bool(real_token), 
        mock_api_success,
        real_api_success,
        mock_rejected,
        real_handled
    ])
    
    print(f"Passed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Authentication separation is working correctly.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Authentication separation needs fixes.")
        sys.exit(1)

if __name__ == "__main__":
    main()
