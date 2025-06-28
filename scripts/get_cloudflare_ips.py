import requests
import ipaddress
import subprocess
import concurrent.futures
import time
import platform
import re # Import regex module

# Cloudflare IP ranges URLs
IPV4_URL = "https://www.cloudflare.com/ips-v4"
IPV6_URL = "https://www.cloudflare.com/ips-v6"

def get_cloudflare_ips(url):
    """Fetches Cloudflare IP ranges from the given URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.text.splitlines()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching IPs from {url}: {e}")
        return []

def test_ip_latency(ip_address, count=4):
    """Tests IP latency using ping and returns the average latency in ms."""
    try:
        # Use -n for Windows, -c for Linux/macOS
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ["ping", param, str(count), ip_address]
        
        # Add a shorter timeout for ping command itself to avoid long waits for unreachable hosts
        # The subprocess.run timeout is for the entire command execution.
        # For ping, we might want a per-ping timeout if supported, but -c handles total packets.
        process = subprocess.run(command, capture_output=True, text=True, timeout=15) # Increased timeout slightly
        
        if process.returncode == 0:
            output = process.stdout
            # Regex to find latency values (e.g., time=X.XXX ms, Time=Xms, avg = X.XXXms)
            # This regex tries to capture various formats for individual ping times or summary averages.
            latency_matches = re.findall(r"time[=<](\d+\.?\d*)\s?ms|Average\s?=\s?(\d+\.?\d*)\s?ms|min/avg/max/mdev\s?=\s?\d+\.?\d*/(\d+\.?\d*)", output, re.IGNORECASE)
            
            latencies = []
            for match in latency_matches:
                # Group 1 for 'time=X.XXX ms', Group 2 for 'Average = X.XXX ms', Group 3 for 'min/avg/max/mdev = .../X.XXX/...'
                if match[0]:
                    latencies.append(float(match[0]))
                elif match[1]:
                    latencies.append(float(match[1]))
                elif match[2]:
                    latencies.append(float(match[2]))

            if latencies:
                return sum(latencies) / len(latencies)
            else:
                print(f"Warning: Could not parse latency from ping output for {ip_address}. Output:\n{output}")
                return float('inf') # Could not parse latency
        else:
            print(f"Ping command failed for {ip_address} with return code {process.returncode}. Stderr: {process.stderr}")
            return float('inf')  # Ping failed
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Error testing IP {ip_address}: {e}")
        return float('inf') # Return infinity for errors

def get_best_ips(ip_list, num_ips=10):
    """Tests a list of IPs and returns the best ones based on latency."""
    best_ips = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_ip = {executor.submit(test_ip_latency, ip): ip for ip in ip_list}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                latency = future.result()
                if latency != float('inf'):
                    best_ips.append((latency, ip))
            except Exception as exc:
                print(f'{ip} generated an exception: {exc}')
    
    # Sort by latency and take the top N
    best_ips.sort(key=lambda x: x[0])
    return [ip for latency, ip in best_ips[:num_ips]]

def write_ips_to_file(filename, ips):
    """Writes a list of IPs to a file, each on a new line."""
    try:
        with open(filename, 'w') as f:
            for ip in ips:
                f.write(f"{ip}\n")
        print(f"Successfully wrote {len(ips)} IPs to {filename}")
    except IOError as e:
        print(f"Error writing to file {filename}: {e}")

def main():
    print("Fetching Cloudflare IPv4 ranges...")
    ipv4_ranges = get_cloudflare_ips(IPV4_URL)
    ipv4_addresses = []
    for ip_range in ipv4_ranges:
        try:
            # Expand CIDR ranges to individual IPs for testing, or just use the range itself
            # For simplicity and to avoid too many pings, we'll just use the CIDR as is for now
            # and let ping handle it, or pick a representative IP from the range.
            # However, pinging a CIDR is not standard. We need to pick an IP from the range.
            # For this task, let's assume we ping the first usable IP in the range.
            network = ipaddress.ip_network(ip_range, strict=False)
            # For simplicity, we'll just add the network address itself to the list for testing
            # In a real scenario, you might want to pick a few IPs from each range or the gateway.
            # For now, let's just add the network address as a representative.
            ipv4_addresses.append(str(next(network.hosts())))
        except ValueError:
            continue # Skip invalid IP ranges

    print("Fetching Cloudflare IPv6 ranges...")
    ipv6_ranges = get_cloudflare_ips(IPV6_URL)
    ipv6_addresses = []
    for ip_range in ipv6_ranges:
        try:
            network = ipaddress.ip_network(ip_range, strict=False)
            # For IPv6, try network_address + 1 first, then fallback to next(network.hosts())
            # This is a common heuristic for IPv6 to get a pingable address.
            try:
                # Attempt to get a common pingable address (e.g., gateway or first host)
                # For IPv6, network_address + 1 is often a good candidate.
                # Or, if the range is small, just use the network address itself if it's a host.
                if network.num_addresses > 1: # Ensure there's at least one host
                    ipv6_addresses.append(str(network.network_address + 1))
                else: # If it's a /128, just use the address itself
                    ipv6_addresses.append(str(network.network_address))
            except TypeError: # Handle cases where network_address + 1 is not directly supported or meaningful
                try:
                    ipv6_addresses.append(str(next(network.hosts())))
                except StopIteration:
                    continue # No usable hosts in this range
        except ValueError:
            continue # Skip invalid IP ranges

    print(f"Found {len(ipv4_addresses)} IPv4 addresses/ranges and {len(ipv6_addresses)} IPv6 addresses/ranges.")

    print("Testing IPv4 addresses for best latency (this may take a while)...")
    best_ipv4s = get_best_ips(ipv4_addresses, num_ips=20)
    write_ips_to_file("cfipv4.txt", best_ipv4s)

    print("Testing IPv6 addresses for best latency (this may take a while)...")
    best_ipv6s = get_best_ips(ipv6_addresses, num_ips=20)
    write_ips_to_file("cfipv6.txt", best_ipv6s)

if __name__ == "__main__":
    main()