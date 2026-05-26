# IPTV 域名解析与自动更新服务

本项目是一个用于 IPTV 订阅源域名解析、IP 优选测速、流媒体播放可用性测试与局域网文件订阅共享的实用工具。

---

## 🛠️ 主要功能特性

1. **防 DNS 劫持与污染**：集成 DoH (DNS-over-HTTPS) 引擎，可绕过本地代理或宽带 DNS 污染劫持，解析出真实的 CDN 节点公网 IP。
2. **多 IP 候选双栈解析**：支持并发获取域名对应的所有可用 IPv6 与 IPv4 候选 IP 列表。
3. **流媒体实际播放测试 (拉流测试)**：
   - 开启 `media_stream_test` 后，会对所有候选 IP 拼装出的独立播放 URL 发起实际的 HTTP GET 拉流测试，读取首个数据块（首包字节）以验证流媒体可用性。
   - 自动过滤并剔除状态码异常（如 403 Forbidden、404 Not Found）或连接成功但服务器无流数据传输的无效链接，保障生成的订阅列表内链接基本可用。
4. **同名电视频道重排序**：支持将相同名字的电视频道（包含跨抓取源的同名频道以及域名解析的多 IP 备选链接）进行合并聚合，并根据流媒体拉流实测的延迟耗时（秒）进行升序排序，将响应最快、最稳定的链接排在最前。
5. **智能双栈保留与备用防线**：在 `"prefer-ipv6"` 智能模式下，系统会无条件同时测试所有的可用 IPv6 和 IPv4 路线，保留所有可播的 IPv6 链接，同时在 IPv4 链接中自动筛选出**延迟最低、最快的前 2 个可用 v4 链接**作为最后的备选防线一并写入。
6. **慢源冗余剔除**：支持通过配置 `"max_channels_per_title"`（默认值为 3）限制同一个同名电视频道保留的最大播放源数量上限。自动保留速度最快的前 N 个极速源，将剩余响应较慢的冗余源自动剔除，使列表保持精炼。
7. **局部数据源精细策略**：支持在 `sources` 数据源列表中为每个网络源单独定制解析模式（如限制为局部 `"ipv6-only"` 或 `"ipv4-only"`），若域名未解析出相应协议的 IP 记录，该频道链接将自动被剔除。
8. **内置 Web 配置后台与共享服务器**：工具内置了 Web 服务器（默认使用 8080 端口），电视端或播放器可直接通过局域网链接 `http://<服务器IP>:8080/output/<文件名>` 订阅播放列表。同时提供可视化配置页面，支持增删改订阅源以及在线查看运行日志。
9. **日志滚动防盘爆**：运行日志会写入 `output/resolver.log`。单个日志文件大小限制最大为 2MB，自动滚动轮转并最多保留最近 3 个备份文件。
10. **流媒体中转代理与电视零配置（全新特性）**：
    - 集成**流媒体代理（Stream Proxy）**服务。在 `config.json` 中配置 `"web_proxy": true` 即可无感开启。
    - **无侵入与免配置**：电视机端不需要修改 hosts 或 root 系统，所有“以 IP 直连请求，但在 TLS 握手和 HTTP 头中保留真实域名（Host & SNI）”的高难防盗链规避动作全部由后台的 Python 代理服务代劳。
    - **高并发与线程隔离**：采用 `threading.local` 技术实现纯净的线程级劫持补丁，播放流媒体完全在独立子线程中运行，互不干扰，不阻塞其他业务或后台解析更新。
    - **自适应局域网 IP**：电视拉取 M3U 时，服务会动态根据请求头将占位符替换为当前的真实 IP（支持局域网、Docker、外网穿透等多变环境），对用户完全透明。

---

## 📂 项目结构

```text
├── config.json          # 核心策略与数据源配置文件
├── config_readme.md     # 配置文件参数详尽指南
├── index.html           # 内置 Web 配置管理后台静态页面
├── iptv_resolver.py     # 核心 Python 解析、测试过滤与 Web 共享服务脚本
├── Dockerfile           # 轻量化 Docker 镜像构建文件 (~35MB)
├── docker-compose.yml   # 一键启动部署配置文件
└── output/
    ├── best_sorted_resolved.m3u  # 优选重排序后的播放列表输出文件
    └── resolver.log              # 本地防爆盘滚动运行日志文件
```

---

## ⚙️ 配置文件参数详解 (`config.json`)

```json
{
  "dns_servers": [],
  "update_interval_hours": 12,
  "keep_unresolved": false,
  "ip_speed_test": true,
  "media_stream_test": true,
  "media_stream_timeout": 3.0,
  "max_channels_per_title": 3,
  "workers": 50,
  "sources": [
    {
      "name": "zilong7728_best_sorted",
      "url": "https://github.com/zilong7728/Collect-IPTV/blob/main/best_sorted.m3u",
      "output": "best_sorted_resolved.m3u"
    },
    {
      "name": "strict_ipv6_only",
      "url": "https://live.zbds.top/tv/iptv6.m3u",
      "output": "cctv_only_v6.m3u",
      "mode": "ipv6-only"
    },
    {
      "name": "strict_ipv4_only",
      "url": "https://live.zbds.top/tv/iptv6.m3u",
      "output": "cctv_only_v4.m3u",
      "mode": "ipv4-only"
    }
  ]
}
```

各配置项详细描述与高阶场景配置方案，请阅读项目内置的 **[config_readme.md](file:///Users/qinzhanbo/Downloads/iptv/config_readme.md)** 指南。

---

## 🐳 Docker Compose 部署运行

在需要部署服务的服务器（如 NAS、软路由或 VPS）上新建一个文件夹，放入 `config.json` 和 `docker-compose.yml` 两个文件，执行以下命令即可启动：

```bash
# 1. 以后台进程模式启动容器
docker compose up -d

# 2. 查看容器运行状态与日志
docker compose logs -f
```

**局域网访问与电视订阅地址说明**（假设您的服务器局域网 IP 是 `192.168.31.5`）：
1. **Web 配置管理后台**：`http://192.168.31.5:8080/`
2. **默认解析测速重排源**：`http://192.168.31.5:8080/output/best_sorted_resolved.m3u`
3. **纯 IPv6 过滤订阅源**：`http://192.168.31.5:8080/output/cctv_only_v6.m3u`
4. **纯 IPv4 过滤订阅源**：`http://192.168.31.5:8080/output/cctv_only_v4.m3u`
5. **在线实时日志查看**：`http://192.168.31.5:8080/output/resolver.log`

---

## 🛠️ 本地手动运行

如果您不想使用 Docker，也可直接通过 Python 3 在本地运行（脚本内置了依赖自动补齐机制，会自动安装 `requests` 和 `dnspython`）：

```bash
python3 iptv_resolver.py -c config.json
```
*(注：手动运行时，若没有将 "web_port" 显式设置为 0，程序在单次执行后会默认以 8080 端口继续在后台运行，以提供局域网文件订阅与 Web 配置后台管理服务。)*
