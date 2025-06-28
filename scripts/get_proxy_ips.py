import requests
import re
import time

def get_proxies():
    """
    从 free-proxy-list.net 获取代理IP列表。
    """
    url = "https://www.sslproxies.org/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 检查HTTP请求是否成功
        
        # 使用正则表达式从响应文本中提取IP地址和端口
        # 查找形如 <td>XXX.XXX.XXX.XXX</td><td>YYYY</td> 的模式
        # For sslproxies.org, the structure is similar to free-proxy-list.net
        proxies = re.findall(r'<td>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td><td>(\d+)</td>', response.text)
        
        # 格式化为 IP:Port
        formatted_proxies = [f"{ip}:{port}" for ip, port in proxies]
        return formatted_proxies
    except requests.exceptions.RequestException as e:
        print(f"获取代理IP失败: {e}")
        return []

def validate_proxy(proxy):
    """
    验证代理IP是否可用。
    """
    test_url = "http://httpbin.org/ip"
    proxies = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}" # 免费代理通常只支持HTTP，但有些网站可能需要HTTPS
    }
    try:
        response = requests.get(test_url, proxies=proxies, timeout=5)
        response.raise_for_status()
        # 检查返回的IP是否与代理IP一致（或至少请求成功）
        if response.json().get('origin'):
            print(f"代理 {proxy} 可用。")
            return True
    except requests.exceptions.RequestException as e:
        # print(f"代理 {proxy} 不可用: {e}")
        pass
    return False

def main():
    print("开始获取代理IP...")
    all_proxies = get_proxies()
    if not all_proxies:
        print("未能获取到任何代理IP，脚本结束。")
        return

    print(f"已获取到 {len(all_proxies)} 个代理IP，开始验证...")
    
    valid_proxies = []
    for proxy in all_proxies:
        if len(valid_proxies) >= 10:
            break
        if validate_proxy(proxy):
            valid_proxies.append(proxy)
        time.sleep(0.1) # 避免请求过快被封禁

    if valid_proxies:
        with open("proxyIP.txt", "w") as f:
            for proxy in valid_proxies:
                f.write(proxy + "\n")
        print(f"已将 {len(valid_proxies)} 个可用代理IP写入 proxyIP.txt 文件。")
    else:
        print("未找到任何可用代理IP。")

if __name__ == "__main__":
    main()