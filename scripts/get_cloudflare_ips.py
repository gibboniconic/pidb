import requests
import ipaddress
import subprocess
import concurrent.futures
import time
import platform

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
        
        start_time = time.time()
        process = subprocess.run(command, capture_output=True, text=True, timeout=10)
        end_time = time.time()

        if process.returncode == 0:
            # Parse ping output for latency
            output = process.stdout
            # Example output: "time=12.345ms" or "avg = 12.345ms"
            # Common patterns for latency in ping output
            # Linux/macOS: "time=X.XXX ms" or "min/avg/max/mdev = X.XXX/Y.YYY/Z.ZZZ/A.AAA ms"
            # Windows: "Time=Xms"
            
            # Try to find "time=" pattern (common for individual pings)
            time_matches = [float(line.split("time=")[1].split(" ")[0].replace("ms", ""))
                            for line in output.splitlines() if "time=" in line]
            if time_matches:
                return sum(time_matches) / len(time_matches)
            
            # Try to find "min/avg/max/" pattern (common for summary on Linux/macOS)
            for line in output.splitlines():
                if "min/avg/max/" in line:
                    try:
                        parts = line.split('=')[1].split('/')
                        return float(parts[1]) # avg latency
                    except (IndexError, ValueError):
                        continue
            
            # Try to find "Average =" pattern (common for summary on Windows)
            for line in output.splitlines():
                if "Average =" in line and "ms" in line:
                    try:
                        latency_str = line.split("Average =")[1].split("ms")[0].strip()
                        return float(latency_str)
                    except (IndexError, ValueError):
                        continue
        
        return float('inf')  # Return infinity for unreachable or unparseable IPs
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
            # For IPv6, network.hosts() might be empty or yield unpingable addresses.
            # Try to get the first usable host address by adding 1 to the network address.
            # This is a common heuristic for IPv6.
            try:
                ipv6_addresses.append(str(network.network_address + 1))
            except TypeError: # Handle cases where network_address + 1 is not directly supported
                # Fallback to next(network.hosts()) if adding 1 fails
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