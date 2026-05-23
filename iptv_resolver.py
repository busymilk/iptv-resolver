#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import socket
import logging
import logging.handlers
import argparse
import threading
import subprocess
import ipaddress
import socketserver
from http.server import SimpleHTTPRequestHandler
from urllib.parse import urlparse, urlunparse, parse_qs
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

# 创建输出目录以保证日志文件能顺利生成
os.makedirs("output", exist_ok=True)
log_path = os.path.join("output", "resolver.log")

# 创建自动滚动轮转的文件日志处理器 (限制最大 2MB，最多保留 3 个备份文件)
file_handler = logging.handlers.RotatingFileHandler(
    log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf-8'
)
stream_handler = logging.StreamHandler(sys.stdout)

# 同时向控制台标准输出和本地归档日志文件打印，防污染
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        file_handler,
        stream_handler
    ]
)

# 确保依赖已加载
ensure_dependencies()
import requests
try:
    import dns.resolver
except ImportError:
    pass

# 全局变量以支持 Web 动态热重载
GLOBAL_CONFIG_PATH = "config.json"
global_config = {}
is_updating_flag = False  # 用于防止并发重复触发解析更新

def load_global_config():
    global global_config
    if os.path.exists(GLOBAL_CONFIG_PATH):
        try:
            with open(GLOBAL_CONFIG_PATH, "r", encoding="utf-8") as f:
                global_config = json.load(f)
            logging.info("全局配置加载/重载成功！")
        except Exception as e:
            logging.error(f"加载全局配置失败: {e}")

load_global_config()

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
    返回: (best_ip, ip_type, best_time)
    """
    domain, port, scheme = domain_key
    
    # 1. 域名解析获取所有 IP 候选列表
    ips_v6, ips_v4 = resolve_domain_all(domain, dns_servers, mode, use_doh)
    if not ips_v6 and not ips_v4:
        return None, None, float('inf')
        
    # 2. 确认测速端口
    test_port = port if port else (443 if scheme == 'https' else 80)
    
    best_ip = None
    best_type = None
    best_time = float('inf')
    
    # 3. 解析策略判定与测速选择
    
    # A. 优先尝试 IPv6
    if mode in ["prefer-ipv6", "ipv6-only"] and ips_v6:
        if do_speed_test and len(ips_v6) > 0:
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
    if not best_ip and mode in ["prefer-ipv6", "ipv4-only"] and ips_v4:
        if do_speed_test and len(ips_v4) > 0:
            for ip in ips_v4:
                cost = test_ip_speed(ip, test_port)
                if cost < best_time:
                    best_time = cost
                    best_ip = ip
                    best_type = 'v4'
        else:
            best_ip = ips_v4[0]
            best_type = 'v4'
            best_time = 0.001
            
    # 4. 极致容错保底设计：
    if not best_ip:
        if mode in ["prefer-ipv6", "ipv6-only"] and ips_v6:
            best_ip = ips_v6[0]
            best_type = 'v6'
        elif mode in ["prefer-ipv6", "ipv4-only"] and ips_v4:
            best_ip = ips_v4[0]
            best_type = 'v4'
            
    return best_ip, best_type, best_time

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
    """处理单个数据源：下载 -> 解析域名 -> 测速优选 -> 重新排序 -> 写入本地"""
    name = source_cfg.get("name")
    url = source_cfg.get("url")
    output_filename = source_cfg.get("output")
    
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
    
    dns_cache = {} # (domain, port, scheme) -> (ip, ip_type, speed_cost)
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_key = {
            executor.submit(resolve_and_select_best, key, dns_servers, mode, use_doh, do_speed_test): key 
            for key in domain_keys_to_resolve
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                ip, ip_type, speed_cost = future.result()
                if ip:
                    dns_cache[key] = (ip, ip_type, speed_cost)
                    logging.debug(f"连接优化成功: {key[0]}:{key[1]} -> {ip} ({ip_type})，延迟: {speed_cost:.4f}s")
                else:
                    dns_cache[key] = (None, None, float('inf'))
                    logging.debug(f"连接优化失败: {key[0]}:{key[1]}")
            except Exception as e:
                dns_cache[key] = (None, None, float('inf'))
                logging.error(f"优化连接 {key[0]} 时发生异常: {e}")
                
    # 3. 双层优化与同名电视频道测速重新排序！
    keep_unresolved = global_cfg.get("keep_unresolved", False)
    
    # 我们创建一个列表，只保存可通行的 channel elements 或者是元数据 elements
    processed_elements = []
    
    # 为同名电视频道做聚合准备
    # 键：电视频道名；值：[channel_element_dict, ...]
    channels_by_title = {}
    
    for el in elements:
        if el["type"] == "meta":
            processed_elements.append(el)
        elif el["type"] == "channel":
            try:
                parsed = urlparse(el["url"])
                domain = parsed.hostname
                port = parsed.port
                scheme = parsed.scheme
                
                key = (domain, port, scheme)
                ip, ip_type, speed_cost = dns_cache.get(key, (None, None, float('inf')))
                
                if ip:
                    # 替换 IP 得到最新的真实 URL
                    new_url = reconstruct_url(el["url"], ip, ip_type)
                    el["url"] = new_url
                    el["speed_cost"] = speed_cost
                    el["resolved"] = True
                    el["ip_type"] = ip_type
                else:
                    el["speed_cost"] = float('inf')
                    el["resolved"] = False
                    
                # 确定电视频道名，用以同名聚合
                channel_title = ""
                if format_type == 'm3u':
                    if ',' in el["info"]:
                        channel_title = el["info"].rsplit(',', 1)[1].strip()
                    if not channel_title:
                        channel_title = el["info"]
                else: # txt
                    channel_title = el["name"]
                    
                el["channel_title"] = channel_title
                
                # 过滤策略判定：
                # 如果解析/测速彻底失败，且 keep_unresolved 为 false，则直接过滤抛弃
                if not el["resolved"] and not keep_unresolved:
                    logging.debug(f"频道 [{channel_title}] 所有 IP 均不可达，已被丢弃")
                    continue
                    
                # 放入同名聚合容器
                if channel_title not in channels_by_title:
                    channels_by_title[channel_title] = []
                channels_by_title[channel_title].append(el)
                
            except Exception as e:
                logging.error(f"处理频道测速替换发生异常: {e}")
                if keep_unresolved:
                    processed_elements.append(el)
                    
    # 4. 同名电视频道测速重新排序！
    # 对聚合好的每个同名电视频道的多个链接，根据测速延迟（speed_cost）升序排序（从小到大，越快越靠前）！
    sorted_channels_list = []
    
    # 我们遍历 elements 以保持文件里电视台原本出现的相对次序！
    # 为了避免重复写入同名电视台，我们需要标记已写入的电视台名称。
    visited_titles = set()
    
    for el in elements:
        if el["type"] == "channel":
            # 找到它的电视频道名
            channel_title = ""
            if format_type == 'm3u':
                if ',' in el["info"]:
                    channel_title = el["info"].rsplit(',', 1)[1].strip()
                if not channel_title:
                    channel_title = el["info"]
            else:
                channel_title = el["name"]
                
            if channel_title in channels_by_title and channel_title not in visited_titles:
                visited_titles.add(channel_title)
                # 获取该电视台下所有的视频源链接
                source_links = channels_by_title[channel_title]
                
                # ⭐️ 核心逻辑：根据 speed_cost（TCP 建立延迟，秒）对多源进行重新排序！
                source_links.sort(key=lambda x: x.get("speed_cost", float('inf')))
                
                # 写入排序后的播放链接
                for link_el in source_links:
                    sorted_channels_list.append(link_el)
                    
    # 5. 输出写出到 output 文件夹
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)
    
    resolved_count = 0
    
    with open(output_path, "w", encoding="utf-8") as f:
        # 首先写入元数据首部行（如 #EXTM3U）
        for el in processed_elements:
            if el["type"] == "meta":
                f.write(el["content"] + "\n")
                
        # 写入重新排序、精细优选后的电视频道链接行
        for el in sorted_channels_list:
            resolved_count += 1
            if format_type == 'm3u':
                # 对重排后的电视台行，可以在逗号后的频道名上优雅加上 [延迟评级] 或是保持原本
                # 这里为了极致的兼容性与原本风格一致，保持原 info 内容写入
                f.write(el["info"] + "\n")
                for extra_meta in el.get("extra", []):
                    f.write(extra_meta + "\n")
                f.write(el["url"] + "\n")
            else: # txt
                f.write(f"{el['name']},{el['url']}\n")
                
    logging.info(f"数据源 [{name}] 处理完毕。")
    logging.info(f"成功测速排序并保留频道链接: {resolved_count} 个")
    logging.info(f"结果已成功输出到: {output_path}\n")

# Web 接口业务逻辑处理 Handler
class WebConfigHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # 默认提供项目 Downloads 目录下的静态网页文件服务
        super().__init__(*args, directory=".", **kwargs)

    def end_headers(self):
        # 允许跨域以便 AJAX 调用更顺畅
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.end_headers()

    def do_GET(self):
        # 根目录重定向到 admin.html 配置后台
        if self.path == "/" or self.path == "/admin":
            self.send_response(302)
            self.send_header('Location', '/admin.html')
            self.end_headers()
            return
            
        # API 1: 获取当前全局配置数据
        if self.path == "/api/config":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            load_global_config()
            self.wfile.write(json.dumps(global_config, ensure_ascii=False, indent=2).encode('utf-8'))
            return
            
        # API 2: 获取当前系统状态
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            status_data = {
                "is_updating": is_updating_flag,
                "current_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "config_loaded": bool(global_config)
            }
            self.wfile.write(json.dumps(status_data).encode('utf-8'))
            return

        # 其他静态文件，回退到标准处理器
        super().do_GET()

    def do_POST(self):
        # API 3: 接收并保存全新配置数据
        if self.path == "/api/save_config":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                new_cfg = json.loads(post_data.decode('utf-8'))
                
                # 写入 config.json 配置文件
                with open(GLOBAL_CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(new_cfg, f, ensure_ascii=False, indent=2)
                    
                # 重新加载内存中的全局变量
                load_global_config()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "配置文件已成功保存并应用！"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": f"保存配置文件失败: {e}"}).encode('utf-8'))
            return

        # API 4: 手动一键触发“立即下载并测速解析”
        if self.path == "/api/trigger_update":
            global is_updating_flag
            if is_updating_flag:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "已有解析更新任务在后台运行中，请勿重复触发。"}).encode('utf-8'))
                return
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "已在后台触发一键更新与多源测速排序任务！"}).encode('utf-8'))
            
            # 后台启动异步线程执行更新
            def async_update():
                global is_updating_flag
                is_updating_flag = True
                try:
                    logging.info("[Web GUI] 接收到手动触发请求，开始新一轮解析测速重排流程...")
                    run_once(GLOBAL_CONFIG_PATH)
                except Exception as e:
                    logging.error(f"[Web GUI] 异步触发解析发生异常: {e}")
                finally:
                    is_updating_flag = False
                    
            t = threading.Thread(target=async_update)
            t.start()
            return

        self.send_response(404)
        self.end_headers()

def start_web_server(port, directory="output"):
    """多线程内置 HTTP / API 服务器，合并共享目录与 GUI 管理后台"""
    class TCPServer(socketserver.TCPServer):
        allow_reuse_address = True
        
    try:
        # 使用自定义的 WebConfigHandler 统一拦截 API 接口和静态页面
        with TCPServer(("", port), WebConfigHandler) as httpd:
            logging.info(f"[微服务 Web 服务器] 启动成功！")
            logging.info(f"👉 局域网 Web 管理配置后台: http://<您的服务器IP>:{port}/admin")
            logging.info(f"👉 电视/播放器订阅文件夹挂在在当前服务端口下，直接访问: http://<您的服务器IP>:{port}/output/<输出文件名>")
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
    
    global GLOBAL_CONFIG_PATH
    GLOBAL_CONFIG_PATH = args.config
    load_global_config()
    
    logging.info("IPTV 域名解析、多 IP 优选与同名重排序服务启动...")
    run_once(GLOBAL_CONFIG_PATH)
    
    interval = global_config.get("update_interval_hours", 0)
    web_port = global_config.get("web_port", 0)
    
    if interval > 0:
        if web_port > 0:
            # 开启内置多用途 Web 共享与 API 服务器
            web_thread = threading.Thread(target=start_web_server, args=(web_port, "output"), daemon=True)
            web_thread.start()
            
        logging.info(f"服务已进入常驻守护进程模式。每 {interval} 小时自动更新与测速排序一次...")
        try:
            while True:
                time.sleep(interval * 3600)
                logging.info("定时更新触发，开始新一轮解析与同名重排流程...")
                run_once(GLOBAL_CONFIG_PATH)
        except KeyboardInterrupt:
            logging.info("服务被用户手动终止。")
    else:
        # 单次执行模式下，如果开启了 web 端口，则主线程挂起以对外提供后台管理和文件订阅服务
        if web_port > 0:
            logging.info(f"单次解析完成。由于开启了 Web 服务且属于单次模式，主线程将挂起以提供局域网后台与分发...")
            start_web_server(web_port, "output")
        else:
            logging.info("单次解析与同名重排任务完毕，程序退出。")

if __name__ == "__main__":
    main()
