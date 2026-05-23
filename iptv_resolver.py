#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import socket
import logging
import argparse
import threading
import subprocess
import ipaddress
import socketserver
from http.server import SimpleHTTPRequestHandler
from urllib.parse import urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# 自动补齐依赖的机制
def ensure_dependencies():
    required = {
        "requests": "requests",
        "dns": "dnspython"
    }
    missing = []
    for module, pip_name in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pip_name)
    
    if missing:
        logging.info(f"检测到缺失依赖: {missing}，正在尝试自动安装...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            logging.info("依赖安装成功！")
        except Exception as e:
            logging.error(f"自动安装依赖失败: {e}。请手动执行: pip install {' '.join(missing)}")
            sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 确保依赖已加载
ensure_dependencies()
import requests
try:
    import dns.resolver
except ImportError:
    pass

def is_ip(host):
    """判断给定的 host 是否已经是 IP 地址（支持 IPv4 和带中括号的 IPv6）"""
    if not host:
        return False
    h = host.strip('[]')
    try:
        ipaddress.ip_address(h)
        return True
    except ValueError:
        return False

# 初始化全局 HTTP Session 并调大连接池以支持高并发
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
http_session.mount('http://', adapter)
http_session.mount('https://', adapter)

def test_ip_speed(ip, port, timeout=1.2):
    """
    测试特定 IP 与端口的 TCP 连接建立速度。
    返回: 连接成功的耗时（秒）。若连接失败或超时，返回 float('inf')。
    """
    start_time = time.perf_counter()
    try:
        af = socket.AF_INET6 if ':' in ip else socket.AF_INET
        s = socket.socket(af, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        cost = time.perf_counter() - start_time
        return cost
    except Exception:
        return float('inf')

def resolve_domain_doh_all(domain, mode="prefer-ipv6"):
    """使用阿里云 DNS-over-HTTPS (DoH) API 获取域名所有的 IPv6 和 IPv4 解析地址列表，防 Fake-IP 污染"""
    ips_v6 = []
    ips_v4 = []

    # 1. 解析 IPv6 (AAAA 记录, type=28)
    if mode in ["prefer-ipv6", "ipv6-only"]:
        try:
            url = f"https://dns.alidns.com/resolve?name={domain}&type=AAAA"
            resp = http_session.get(url, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                if "Answer" in data:
                    for ans in data["Answer"]:
                        if ans.get("type") == 28 and ans.get("data"):
                            ips_v6.append(ans["data"])
        except Exception as e:
            logging.debug(f"DoH AAAA 解析 {domain} 出错: {e}")

    # 2. 解析 IPv4 (A 记录, type=1)
    if mode in ["prefer-ipv6", "ipv4-only"] or (mode == "prefer-ipv6" and not ips_v6):
        try:
            url = f"https://dns.alidns.com/resolve?name={domain}&type=A"
            resp = http_session.get(url, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                if "Answer" in data:
                    for ans in data["Answer"]:
                        if ans.get("type") == 1 and ans.get("data"):
                            ips_v4.append(ans["data"])
        except Exception as e:
            logging.debug(f"DoH A 解析 {domain} 出错: {e}")

    return ips_v6, ips_v4

def resolve_domain_all(domain, dns_servers=None, mode="prefer-ipv6", use_doh=True):
    """
    智能解析域名，返回该域名对应的所有 IP 列表：(ips_v6, ips_v4)
    """
    if is_ip(domain):
        h = domain.strip('[]')
        if ':' in h:
            return [h], []
        else:
            return [], [h]

    # 1. 优先使用 DoH（若启用且无自定义传统 DNS）
    if use_doh and not dns_servers:
        ips_v6, ips_v4 = resolve_domain_doh_all(domain, mode)
        if ips_v6 or ips_v4:
            return ips_v6, ips_v4

    ips_v6 = []
    ips_v4 = []

    # 2. 使用自定义 DNS 服务器解析 (传统 UDP/TCP 方式)
    if dns_servers:
        try:
            resolver = dns.resolver.Resolver(configure=False)
            resolver.nameservers = dns_servers
            resolver.timeout = 2.0
            resolver.lifetime = 2.0

            if mode in ["prefer-ipv6", "ipv6-only"]:
                try:
                    answers = resolver.resolve(domain, 'AAAA')
                    ips_v6 = [str(rdata) for rdata in answers]
                except Exception:
                    pass

            if mode in ["prefer-ipv6", "ipv4-only"] or (mode == "prefer-ipv6" and not ips_v6):
                try:
                    answers = resolver.resolve(domain, 'A')
                    ips_v4 = [str(rdata) for rdata in answers]
                except Exception:
                    pass
        except Exception as e:
            logging.debug(f"自定义 DNS 解析 {domain} 出错: {e}")
    
    # 3. 使用系统默认 DNS 解析
    if not ips_v6 and not ips_v4:
        if mode in ["prefer-ipv6", "ipv6-only"]:
            try:
                results = socket.getaddrinfo(domain, None, socket.AF_INET6)
                ips_v6 = list(set([r[4][0] for r in results if r[4][0]]))
            except Exception:
                pass
        
        if mode in ["prefer-ipv6", "ipv4-only"] or (mode == "prefer-ipv6" and not ips_v6):
            try:
                results = socket.getaddrinfo(domain, None, socket.AF_INET)
                ips_v4 = list(set([r[4][0] for r in results if r[4][0]]))
            except Exception:
                pass

    return ips_v6, ips_v4

def resolve_and_select_best(domain_key, dns_servers, mode, use_doh, do_speed_test=True):
    """
    并发解析域名，并通过连接测速，在解析到的多个 IP 中选出延迟最小、最稳定的最优 IP。
    domain_key: (domain, port, scheme)
    返回: (best_ip, ip_type)
    """
    domain, port, scheme = domain_key
    
    # 1. 域名解析获取所有 IP 候选列表
    ips_v6, ips_v4 = resolve_domain_all(domain, dns_servers, mode, use_doh)
    if not ips_v6 and not ips_v4:
        return None, None
        
    # 2. 确认测速端口
    test_port = port if port else (443 if scheme == 'https' else 80)
    
    best_ip = None
    best_type = None
    best_time = float('inf')
    
    # 3. 解析策略判定与测速选择
    
    # A. 优先尝试 IPv6
    if mode in ["prefer-ipv6", "ipv6-only"] and ips_v6:
        if do_speed_test and len(ips_v6) > 1:
            logging.debug(f"对域名 {domain} 拥有的 {len(ips_v6)} 个 IPv6 地址发起连接测速优选...")
            for ip in ips_v6:
                cost = test_ip_speed(ip, test_port)
                if cost < best_time:
                    best_time = cost
                    best_ip = ip
                    best_type = 'v6'
        else:
            best_ip = ips_v6[0]
            best_type = 'v6'
            best_time = 0.001

    # B. 尝试 IPv4
    # - 若 mode 为 prefer-ipv6，且 IPv6 没解析到，或者虽然解析到但全部 IPv6 测速超时不通，回退尝试 IPv4
    # - 若 mode 为 ipv4-only 且存在 IPv4
    if not best_ip and mode in ["prefer-ipv6", "ipv4-only"] and ips_v4:
        if do_speed_test and len(ips_v4) > 1:
            logging.debug(f"对域名 {domain} 拥有的 {len(ips_v4)} 个 IPv4 地址发起连接测速优选...")
            for ip in ips_v4:
                cost = test_ip_speed(ip, test_port)
                if cost < best_time:
                    best_time = cost
                    best_ip = ip
                    best_type = 'v4'
        else:
            best_ip = ips_v4[0]
            best_type = 'v4'
            
    # 4. 极致容错保底设计：
    # 如果开启了连接测速，但所有可通行的 IP 在当前用户的网络环境下都超时了（导致 best_ip 仍为 None），
    # 为了防止因为测速超时误伤导致频道丢失，我们回退选取第一个解析出的 IP 做保底。
    if not best_ip:
        if mode in ["prefer-ipv6", "ipv6-only"] and ips_v6:
            best_ip = ips_v6[0]
            best_type = 'v6'
        elif mode in ["prefer-ipv6", "ipv4-only"] and ips_v4:
            best_ip = ips_v4[0]
            best_type = 'v4'
            
    return best_ip, best_type

def download_source(url):
    """从网络下载 IPTV 列表，返回内容文本"""
    if "github.com" in url and "/blob/" in url:
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        logging.info(f"检测到 GitHub 网页链接，已自动转换为 Raw 链接: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        return response.text
    except Exception as e:
        logging.error(f"下载数据源失败 {url}: {e}")
        return None

def parse_iptv_content(content):
    """
    将 IPTV 内容解析为结构化列表。
    支持 M3U (含有 #EXTM3U) 和 TXT 格式。
    返回: (format_type, elements)
    """
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return 'unknown', []

    is_m3u = False
    for line in lines[:5]:
        if line.upper().startswith('#EXTM3U'):
            is_m3u = True
            break

    elements = []
    
    if is_m3u:
        format_type = 'm3u'
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.upper().startswith('#EXTM3U'):
                elements.append({"type": "meta", "content": line})
                i += 1
            elif line.startswith('#EXTINF:'):
                info_line = line
                i += 1
                url_line = None
                extra_meta = []
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.startswith('#'):
                        extra_meta.append(next_line)
                        i += 1
                    else:
                        url_line = next_line
                        i += 1
                        break
                
                if url_line:
                    elements.append({
                        "type": "channel",
                        "info": info_line,
                        "url": url_line,
                        "original_url": url_line,
                        "extra": extra_meta
                    })
                else:
                    elements.append({"type": "meta", "content": info_line})
                    for meta in extra_meta:
                        elements.append({"type": "meta", "content": meta})
            else:
                elements.append({"type": "meta", "content": line})
                i += 1
    else:
        format_type = 'txt'
        for line in lines:
            if ',' in line:
                parts = line.split(',', 1)
                name = parts[0].strip()
                url = parts[1].strip()
                if url.lower().startswith(('http://', 'https://', 'rtsp://', 'rtmp://')):
                    elements.append({
                        "type": "channel",
                        "name": name,
                        "url": url,
                        "original_url": url
                    })
                else:
                    elements.append({"type": "meta", "content": line})
            else:
                elements.append({"type": "meta", "content": line})

    return format_type, elements

def reconstruct_url(url, ip, ip_type):
    """使用解析后的 IP 重新组装 URL，正确处理 IPv6 和端口"""
    parsed = urlparse(url)
    port = parsed.port
    
    new_host = f"[{ip}]" if ip_type == 'v6' else ip
    
    if port:
        new_netloc = f"{new_host}:{port}"
    else:
        new_netloc = new_host
        
    new_parsed = parsed._replace(netloc=new_netloc)
    return urlunparse(new_parsed)

def process_source(source_cfg, global_cfg):
    """处理单个数据源：下载 -> 解析域名 -> 测速优选 -> 重新拼接 -> 写入本地"""
    name = source_cfg.get("name")
    url = source_cfg.get("url")
    output_filename = source_cfg.get("output")
    
    # 局部优先级模式：如果数据源配置中指定了 mode，则覆盖全局的 mode 配置
    mode = source_cfg.get("mode", global_cfg.get("mode", "prefer-ipv6"))
    
    logging.info(f"=== 开始处理数据源 [{name}] (解析策略: {mode.upper()}) ===")
    
    content = download_source(url)
    if not content:
        logging.error(f"数据源 [{name}] 下载失败，跳过本次处理。")
        return
        
    format_type, elements = parse_iptv_content(content)
    logging.info(f"数据源格式: {format_type.upper()}, 共解析出 {len(elements)} 行数据")
    
    # 1. 提取所有唯一的 (domain, port, scheme) 组合进行独立解析和测速
    domain_keys_to_resolve = set()
    for el in elements:
        if el["type"] == "channel":
            try:
                parsed = urlparse(el["url"])
                domain = parsed.hostname
                port = parsed.port
                scheme = parsed.scheme
                if domain:
                    domain_keys_to_resolve.add((domain, port, scheme))
            except Exception:
                pass
                
    logging.info(f"需要解析与测速的唯一目标连接数量: {len(domain_keys_to_resolve)}")
    
    # 2. 并发解析与测速优选
    workers = global_cfg.get("workers", 50)
    dns_servers = global_cfg.get("dns_servers", [])
    use_doh = global_cfg.get("use_doh", True)
    do_speed_test = global_cfg.get("ip_speed_test", True)
    
    dns_cache = {} # (domain, port, scheme) -> (ip, ip_type)
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_key = {
            executor.submit(resolve_and_select_best, key, dns_servers, mode, use_doh, do_speed_test): key 
            for key in domain_keys_to_resolve
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                ip, ip_type = future.result()
                if ip:
                    dns_cache[key] = (ip, ip_type)
                    logging.debug(f"连接优化成功: {key[0]}:{key[1]} -> {ip} ({ip_type})")
                else:
                    logging.debug(f"连接优化失败: {key[0]}:{key[1]}")
            except Exception as e:
                logging.error(f"优化连接 {key[0]} 时发生异常: {e}")
                
    # 3. 替换 URL 并输出到 output 文件夹
    keep_unresolved = global_cfg.get("keep_unresolved", False)
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)
    
    resolved_count = 0
    filtered_count = 0
    
    with open(output_path, "w", encoding="utf-8") as f:
        for el in elements:
            if el["type"] == "meta":
                f.write(el["content"] + "\n")
            elif el["type"] == "channel":
                try:
                    parsed = urlparse(el["url"])
                    domain = parsed.hostname
                    port = parsed.port
                    scheme = parsed.scheme
                    
                    key = (domain, port, scheme)
                    
                    if key in dns_cache:
                        ip, ip_type = dns_cache[key]
                        new_url = reconstruct_url(el["url"], ip, ip_type)
                        resolved_count += 1
                        
                        if format_type == 'm3u':
                            f.write(el["info"] + "\n")
                            for extra_meta in el.get("extra", []):
                                f.write(extra_meta + "\n")
                            f.write(new_url + "\n")
                        else: # txt
                            f.write(f"{el['name']},{new_url}\n")
                    else:
                        if keep_unresolved:
                            resolved_count += 1
                            if format_type == 'm3u':
                                f.write(el["info"] + "\n")
                                for extra_meta in el.get("extra", []):
                                    f.write(extra_meta + "\n")
                                f.write(el["url"] + "\n")
                            else: # txt
                                f.write(f"{el['name']},{el['url']}\n")
                        else:
                            filtered_count += 1
                            logging.debug(f"频道 [{el.get('info') or el.get('name')}] 解析/测速失败，已被过滤")
                except Exception as e:
                    logging.error(f"替换 URL 发生异常: {e}")
                    if keep_unresolved:
                        f.write(el["content"] + "\n")
                        
    logging.info(f"数据源 [{name}] 处理完毕。")
    logging.info(f"解析并选出最优 IP 频道: {resolved_count} 个，失败被过滤频道: {filtered_count} 个")
    logging.info(f"结果已成功输出到: {output_path}\n")

def start_web_server(port, directory="output"):
    """多线程内置 HTTP 共享服务器，将 output 目录直接广播到局域网"""
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            # 将 Handler 重定向为专门提供 directory 指定目录的文件服务
            super().__init__(*args, directory=directory, **kwargs)
            
    class TCPServer(socketserver.TCPServer):
        # 允许端口快速释放与复用，防止重启时报 Address already in use
        allow_reuse_address = True
        
    try:
        with TCPServer(("", port), Handler) as httpd:
            logging.info(f"[局域网共享] 服务已成功启动！")
            logging.info(f"👉 局域网电视/播放器订阅地址: http://<您的服务器IP>:{port}/<输出文件名>")
            httpd.serve_forever()
    except Exception as e:
        logging.error(f"启动局域网共享 Web 服务失败: {e}")

def run_once(config_path):
    """单次运行流程"""
    if not os.path.exists(config_path):
        logging.error(f"配置文件未找到: {config_path}")
        sys.exit(1)
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        logging.error(f"读取配置文件失败: {e}")
        sys.exit(1)
        
    sources = cfg.get("sources", [])
    if not sources:
        logging.warning("配置文件中未定义任何 IPTV 数据源。")
        return
        
    for src in sources:
        try:
            process_source(src, cfg)
        except Exception as e:
            logging.error(f"处理数据源 {src.get('name')} 时发生未捕获异常: {e}")

def main():
    parser = argparse.ArgumentParser(description="IPTV 智能域名解析与自动更新工具")
    parser.add_argument("-c", "--config", default="config.json", help="配置文件路径 (默认: config.json)")
    args = parser.parse_args()
    
    logging.info("IPTV 域名解析与 IP 优选服务启动...")
    run_once(args.config)
    
    try:
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
        
    # 局域网 Web 共享服务器启动 (在常驻运行模式下)
    interval = cfg.get("update_interval_hours", 0)
    web_port = cfg.get("web_port", 0)
    
    if interval > 0:
        if web_port > 0:
            web_thread = threading.Thread(target=start_web_server, args=(web_port, "output"), daemon=True)
            web_thread.start()
            
        logging.info(f"服务已进入常驻守护进程模式。每 {interval} 小时自动更新一次...")
        try:
            while True:
                time.sleep(interval * 3600)
                logging.info("定时更新触发，开始新一轮解析与测速流程...")
                run_once(args.config)
        except KeyboardInterrupt:
            logging.info("服务被用户手动终止。")
    else:
        # 单次执行模式下，如果开启了 web 端口，则需要挂起主线程以提供 Web 服务，否则主线程退出就无法访问了
        if web_port > 0:
            logging.info(f"单次解析完成。由于开启了局域网共享且属于单次模式，主线程将挂起以提供 Web 服务...")
            start_web_server(web_port, "output")
        else:
            logging.info("单次解析任务执行完毕，程序退出。")

if __name__ == "__main__":
    main()
