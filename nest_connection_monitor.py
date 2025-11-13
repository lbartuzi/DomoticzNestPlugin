#!/usr/bin/env python3
"""
Nest Connection Monitor
Diagnoses and monitors connection issues with Nest SDM API
"""

import requests
import json
import time
import sys
from datetime import datetime
import socket
import ssl

class NestConnectionMonitor:
    def __init__(self):
        self.token_file = "nest_tokens.json"
        self.log_file = "nest_connection.log"
        self.load_tokens()
    
    def load_tokens(self):
        """Load tokens from file"""
        try:
            with open(self.token_file, "r") as f:
                self.tokens = json.load(f)
                return True
        except:
            print("✗ Failed to load tokens. Run nest_token_manager.py first.")
            sys.exit(1)
    
    def log(self, message, level="INFO"):
        """Log message to file and console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        print(log_entry)
        
        try:
            with open(self.log_file, "a") as f:
                f.write(log_entry + "\n")
        except:
            pass
    
    def test_dns_resolution(self):
        """Test DNS resolution for Google APIs"""
        self.log("Testing DNS resolution...")
        
        hosts = [
            "oauth2.googleapis.com",
            "smartdevicemanagement.googleapis.com",
            "accounts.google.com"
        ]
        
        all_resolved = True
        for host in hosts:
            try:
                ip = socket.gethostbyname(host)
                self.log(f"  ✓ {host} → {ip}")
            except socket.gaierror as e:
                self.log(f"  ✗ {host}: DNS resolution failed - {e}", "ERROR")
                all_resolved = False
        
        return all_resolved
    
    def test_ssl_connection(self):
        """Test SSL/TLS connection to Google APIs"""
        self.log("Testing SSL connections...")
        
        hosts = [
            ("oauth2.googleapis.com", 443),
            ("smartdevicemanagement.googleapis.com", 443)
        ]
        
        all_connected = True
        for host, port in hosts:
            try:
                context = ssl.create_default_context()
                with socket.create_connection((host, port), timeout=5) as sock:
                    with context.wrap_socket(sock, server_hostname=host) as ssock:
                        self.log(f"  ✓ {host}:{port} - SSL {ssock.version()}")
            except Exception as e:
                self.log(f"  ✗ {host}:{port} - {e}", "ERROR")
                all_connected = False
        
        return all_connected
    
    def test_token_validity(self):
        """Check if current token is valid"""
        self.log("Testing token validity...")
        
        # Check token expiry
        expires_at = self.tokens.get("expires_at")
        if expires_at:
            expiry_time = datetime.fromisoformat(expires_at)
            now = datetime.now()
            
            if expiry_time < now:
                self.log(f"  ✗ Token expired at {expires_at}", "WARNING")
                return False
            else:
                time_left = (expiry_time - now).total_seconds()
                self.log(f"  ✓ Token valid for {int(time_left/60)} minutes")
        
        # Test token with API
        headers = {
            "Authorization": f"Bearer {self.tokens.get('access_token')}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(
                "https://smartdevicemanagement.googleapis.com/v1/enterprises",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 401:
                self.log("  ✗ Token rejected by API (401 Unauthorized)", "ERROR")
                return False
            elif response.status_code == 200:
                self.log("  ✓ Token accepted by API")
                return True
            else:
                self.log(f"  ? Unexpected response: {response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"  ✗ API test failed: {e}", "ERROR")
            return False
    
    def test_api_connectivity(self, enterprise_id):
        """Test full API connectivity"""
        self.log("Testing API connectivity...")
        
        headers = {
            "Authorization": f"Bearer {self.tokens.get('access_token')}",
            "Content-Type": "application/json"
        }
        
        url = f"https://smartdevicemanagement.googleapis.com/v1/enterprises/{enterprise_id}/devices"
        
        # Test with different timeouts
        timeouts = [5, 10, 30]
        
        for timeout in timeouts:
            try:
                self.log(f"  Attempting with {timeout}s timeout...")
                start_time = time.time()
                
                response = requests.get(url, headers=headers, timeout=timeout)
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    devices = response.json().get("devices", [])
                    self.log(f"    ✓ Success in {elapsed:.2f}s - {len(devices)} devices found")
                    return True
                else:
                    self.log(f"    ✗ HTTP {response.status_code} in {elapsed:.2f}s", "ERROR")
                    
            except requests.exceptions.Timeout:
                self.log(f"    ✗ Timeout after {timeout}s", "WARNING")
                continue
            except requests.exceptions.ConnectionError as e:
                self.log(f"    ✗ Connection error: {e}", "ERROR")
                continue
            except Exception as e:
                self.log(f"    ✗ Unexpected error: {e}", "ERROR")
                continue
        
        return False
    
    def continuous_monitor(self, enterprise_id, interval=30):
        """Continuously monitor connection health"""
        self.log(f"Starting continuous monitoring (interval: {interval}s)")
        self.log("Press Ctrl+C to stop\n")
        
        success_count = 0
        fail_count = 0
        
        try:
            while True:
                self.log("-" * 60)
                self.log(f"Check #{success_count + fail_count + 1}")
                
                # Run all tests
                dns_ok = self.test_dns_resolution()
                ssl_ok = self.test_ssl_connection()
                token_ok = self.test_token_validity()
                api_ok = self.test_api_connectivity(enterprise_id) if (dns_ok and ssl_ok and token_ok) else False
                
                # Summary
                if api_ok:
                    success_count += 1
                    self.log(f"\n✓ All tests passed! (Success: {success_count}, Fail: {fail_count})")
                else:
                    fail_count += 1
                    self.log(f"\n✗ Some tests failed! (Success: {success_count}, Fail: {fail_count})", "ERROR")
                
                # Calculate success rate
                total = success_count + fail_count
                if total > 0:
                    success_rate = (success_count / total) * 100
                    self.log(f"Success rate: {success_rate:.1f}%")
                
                # Wait for next check
                self.log(f"\nNext check in {interval} seconds...\n")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.log("\n\nMonitoring stopped by user")
            self.log(f"Final stats: Success: {success_count}, Fail: {fail_count}")
    
    def diagnose_transport_error(self):
        """Diagnose 'Transport endpoint is not connected' error"""
        self.log("="*60)
        self.log("DIAGNOSING TRANSPORT ENDPOINT ERROR")
        self.log("="*60)
        
        # Check network interface
        self.log("\n1. Checking network interfaces...")
        try:
            import subprocess
            result = subprocess.run(["ip", "a"], capture_output=True, text=True)
            if "UP" in result.stdout:
                self.log("  ✓ Network interfaces are up")
            else:
                self.log("  ✗ Network interface issues detected", "WARNING")
        except:
            self.log("  ? Could not check network interfaces")
        
        # Check firewall
        self.log("\n2. Checking outbound connections...")
        test_sites = [
            ("google.com", 443),
            ("8.8.8.8", 53),
        ]
        
        for host, port in test_sites:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    self.log(f"  ✓ Can connect to {host}:{port}")
                else:
                    self.log(f"  ✗ Cannot connect to {host}:{port}", "WARNING")
            except:
                self.log(f"  ✗ Failed to test {host}:{port}", "ERROR")
        
        # Check system resources
        self.log("\n3. Checking system resources...")
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent < 80:
                self.log(f"  ✓ CPU usage: {cpu_percent}%")
            else:
                self.log(f"  ⚠ High CPU usage: {cpu_percent}%", "WARNING")
            
            # Memory usage
            memory = psutil.virtual_memory()
            if memory.percent < 80:
                self.log(f"  ✓ Memory usage: {memory.percent}%")
            else:
                self.log(f"  ⚠ High memory usage: {memory.percent}%", "WARNING")
            
            # Check open files/sockets
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            self.log(f"  ℹ File descriptor limit: {soft}/{hard}")
            
        except ImportError:
            self.log("  ? Install psutil for detailed system info (pip install psutil)")
        except:
            self.log("  ? Could not check system resources")
        
        # Recommendations
        self.log("\n" + "="*60)
        self.log("RECOMMENDATIONS:")
        self.log("="*60)
        self.log("\n1. Restart Domoticz service:")
        self.log("   sudo systemctl restart domoticz")
        self.log("\n2. Check Domoticz logs:")
        self.log("   tail -f /var/log/domoticz/domoticz.log")
        self.log("\n3. Increase connection limits if needed:")
        self.log("   ulimit -n 4096")
        self.log("\n4. Check for network issues:")
        self.log("   ping -c 4 smartdevicemanagement.googleapis.com")
        self.log("\n5. Restart networking if needed:")
        self.log("   sudo systemctl restart networking")

def main():
    """Main menu"""
    monitor = NestConnectionMonitor()
    
    print("\n" + "="*60)
    print("NEST CONNECTION MONITOR")
    print("="*60)
    
    # Get enterprise ID
    enterprise_id = input("\nEnter your Enterprise ID (numbers only): ").strip()
    
    while True:
        print("\n" + "-"*60)
        print("1. Run all diagnostic tests")
        print("2. Continuous monitoring")
        print("3. Diagnose transport endpoint error")
        print("4. View connection log")
        print("5. Exit")
        print("-"*60)
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            print()
            monitor.test_dns_resolution()
            monitor.test_ssl_connection()
            monitor.test_token_validity()
            monitor.test_api_connectivity(enterprise_id)
        
        elif choice == "2":
            interval = input("\nMonitoring interval in seconds (default 30): ").strip()
            interval = int(interval) if interval else 30
            monitor.continuous_monitor(enterprise_id, interval)
        
        elif choice == "3":
            print()
            monitor.diagnose_transport_error()
        
        elif choice == "4":
            try:
                with open(monitor.log_file, "r") as f:
                    print("\n" + "="*60)
                    print("RECENT LOG ENTRIES (last 50 lines)")
                    print("="*60)
                    lines = f.readlines()
                    for line in lines[-50:]:
                        print(line.rstrip())
            except:
                print("\n✗ No log file found")
        
        elif choice == "5":
            print("\n👋 Goodbye!")
            break
        
        else:
            print("\n✗ Invalid option")

if __name__ == "__main__":
    main()
