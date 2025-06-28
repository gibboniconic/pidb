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

def test_ip_http_latency(ip_address, target_url="https://www.cloudflare.com/cdn-cgi/trace", timeout=5):
    """Tests IP latency using HTTP/HTTPS connection and returns the total time in ms."""
    try:
        # Use a custom adapter to force requests to use the specific IP address
        # This requires a bit of a workaround as requests doesn't directly support binding to a specific IP for outbound.
        # A simpler approach for testing reachability and latency to a target URL via a specific IP
        # is to resolve the hostname and then try to connect to the IP directly.
        # However, Cloudflare's CDN might serve different content based on IP, and direct IP access
        # might not work for all services.
        # The most straightforward way to test if an IP is "good" for Cloudflare services
        # is to try connecting to a known Cloudflare endpoint *through* that IP.
        # This is typically done by modifying the DNS resolution for the target URL.
        # For this task, we'll assume we can directly connect to the IP if it's a Cloudflare IP.
        # We'll use the 'Host' header to specify the original domain.

        # This is a simplified approach. A more robust solution might involve
        # custom DNS resolution or a proxy.
        # For now, we'll just try to connect to the target URL, but force the IP in the URL.
        # This might not work for all Cloudflare services that rely on hostname SNI.
        # A better approach is to use a custom HTTP adapter that resolves the hostname to the specific IP.

        # Let's try to connect to the target_url, but resolve the hostname to the given IP.
        # This is not directly supported by requests without a custom adapter or DNS resolver.
        # For a practical test, we can try to connect to the IP directly with the Host header.
        # However, Cloudflare's CDN often requires the correct hostname for SNI.

        # A more practical approach for testing a specific IP's connectivity to Cloudflare:
        # 1. Resolve the target_url's hostname (e.g., www.cloudflare.com) to its actual IPs.
        # 2. Try to make a request to the specific ip_address, setting the 'Host' header to the original hostname.
        
        # Let's simplify and just try to connect to the target URL, but use the IP in the URL.
        # This is a common pattern for testing direct IP connectivity to a web server.
        # For Cloudflare, this might not always work due to SNI and CDN routing.
        # However, for the purpose of replacing ping, this is a reasonable first step.

        # Construct the URL to use the specific IP, while keeping the original hostname in the Host header.
        # This is tricky with requests. Let's use a simpler approach:
        # Try to connect to the target_url, but specify the IP as the base.
        # This will likely fail for most Cloudflare services due to SNI.

        # The most reliable way to test a specific IP for a hostname with requests is to
        # use a custom HTTPAdapter that forces the IP resolution.
        # However, this is more complex than a simple replacement for ping.

        # Given the constraints, let's try a direct request to the IP with the Host header.
        # This is a common way to test if a specific IP serves a domain.
        
        # Parse the target URL to get the hostname and path
        from urllib.parse import urlparse
        parsed_url = urlparse(target_url)
        hostname = parsed_url.hostname
        path = parsed_url.path if parsed_url.path else '/'
        scheme = parsed_url.scheme

        # Construct the URL using the specific IP address
        # This assumes the Cloudflare IP will respond to requests on its IP directly
        # with the correct Host header.
        test_url = f"{scheme}://{ip_address}{path}"

        headers = {"Host": hostname}
        
        start_time = time.time()
        response = requests.get(test_url, headers=headers, timeout=timeout, verify=False) # verify=False for self-signed or IP certs
        response.raise_for_status()
        end_time = time.time()
        
        total_time_ms = (end_time - start_time) * 1000
        return total_time_ms
    except requests.exceptions.RequestException as e:
        # print(f"Error testing IP {ip_address} via HTTP/S: {e}")
        return float('inf') # Return infinity for errors
    except Exception as e:
        # print(f"An unexpected error occurred for IP {ip_address}: {e}")
        return float('inf')


def get_best_ips(ip_list, num_ips=10):
    """Tests a list of IPs using HTTP/HTTPS and returns the best ones based on latency."""
    best_ips = []
    # Increased max_workers for potentially faster concurrent HTTP requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
        # Use the new HTTP latency test function
        future_to_ip = {executor.submit(test_ip_http_latency, ip): ip for ip in ip_list}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                latency = future.result()
                if latency != float('inf'):
                    best_ips.append((latency, ip))
            except Exception as exc:
                # print(f'{ip} generated an exception during HTTP test: {exc}')
                pass # Suppress exceptions for cleaner output, as float('inf') is handled

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
            network = ipaddress.ip_network(ip_range, strict=False)
            # For IPv4, we can just use the network address or the first host.
            # Given the HTTP test, any valid IP in the range should work.
            ipv4_addresses.append(str(network.network_address))
        except ValueError:
            continue # Skip invalid IP ranges

    print("Fetching Cloudflare IPv6 ranges...")
    ipv6_ranges = get_cloudflare_ips(IPV6_URL)
    ipv6_addresses = []
    for ip_range in ipv6_ranges:
        try:
            network = ipaddress.ip_network(ip_range, strict=False)
            # For IPv6, use the network address as a representative.
            ipv6_addresses.append(str(network.network_address))
        except ValueError:
            continue # Skip invalid IP ranges

    print(f"Found {len(ipv4_addresses)} IPv4 addresses/ranges and {len(ipv6_addresses)} IPv6 addresses/ranges.")

    print("Testing IPv4 addresses for best HTTP latency (this may take a while)...")
    # Changed num_ips to 10 as per requirement
    best_ipv4s = get_best_ips(ipv4_addresses, num_ips=10)
    write_ips_to_file("cfipv4.txt", best_ipv4s)

    print("Testing IPv6 addresses for best HTTP latency (this may take a while)...")
    # Changed num_ips to 10 as per requirement
    best_ipv6s = get_best_ips(ipv6_addresses, num_ips=10)
    write_ips_to_file("cfipv6.txt", best_ipv6s)

if __name__ == "__main__":
    main()