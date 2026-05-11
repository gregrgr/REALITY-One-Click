# Xray VLESS REALITY One-Click

Ubuntu 22.04 VPS 一键部署 Xray VLESS + REALITY 服务端脚本项目，内置 Clash Meta 订阅、HTTPS 加密订阅地址和轻量管理后端。

> 本项目用于自有服务器、授权网络访问和合法合规的隐私连接场景。请遵守服务器所在地和使用所在地的法律法规。

## 当前状态

已初始化为可开发仓库，首版包含：

- `install.sh`：Ubuntu 22.04 一键安装入口，支持交互式和环境变量安装。
- `uninstall.sh` / `upgrade.sh`：卸载和升级入口。
- `scripts/`：Xray、Nginx、证书、后端、UFW 的安装模块。
- `panel/`：完整 FastAPI Web 管理后端、SQLite 数据层、单节点 Clash/VLESS 订阅生成、Xray 配置生成、流量统计、CLI。
- `templates/`：Nginx HTTP/HTTPS 和 systemd 模板。
- `tests/`：核心配置和订阅生成测试。
- `docs/`：配置、API、排障文档。

## 快速开始

在干净的 Ubuntu 22.04 VPS 上执行：

```bash
git clone <this-repo-url> proxy-panel
cd proxy-panel
bash install.sh
```

非交互安装示例：

```bash
PANEL_DOMAIN=panel.example.com \
ACME_EMAIL=admin@example.com \
ADMIN_USER=admin \
ADMIN_PASSWORD='change-this-password' \
bash install.sh --assume-yes
```

交互式安装时，VPS 本机监听地址和端口会直接使用默认值，不再逐项询问：

- `PUBLIC_HOST` 默认使用 `PANEL_DOMAIN`，订阅里的代理地址写域名。
- `XRAY_LISTEN=0.0.0.0`
- `XRAY_PORT=443`
- `PANEL_HTTPS_PORT=8443`
- `XRAY_API_HOST=127.0.0.1`
- `XRAY_API_PORT=10085`

需要自定义时再通过环境变量覆盖即可，例如 `PUBLIC_HOST=proxy.example.com bash install.sh`。

Cloudflare DNS API 证书签发示例：

```bash
PANEL_DOMAIN=panel.example.com \
ACME_EMAIL=admin@example.com \
ADMIN_PASSWORD='change-this-password' \
ACME_CHALLENGE=cloudflare \
CLOUDFLARE_API_TOKEN='your-cloudflare-api-token' \
bash install.sh --assume-yes
```

安装前请确保：

- `panel.example.com` 已解析到 VPS。
- VPS 安全组/防火墙放行 `80/tcp`、`443/tcp` 和后台端口 `8443/tcp`。
- 服务器没有其他服务占用 `80` 或 `443`。

本地开发验证：

```bash
python -m compileall panel tests
python -m unittest discover -s tests -v
```

Docker 仅作为开发烟测工具，不提供 Docker 部署模式。烟测示例：

```bash
docker run --rm -v "$PWD:/workspace:ro" -w /workspace ubuntu:22.04 \
  bash -lc 'bash -n install.sh uninstall.sh upgrade.sh scripts/*.sh'
```

## 需求分析

### 核心目标

- 在 Ubuntu 22.04 VPS 上一键安装并配置 Xray Core。
- 部署 VLESS + REALITY 入站，默认使用 `xtls-rprx-vision`。
- 支持交互式输入域名、邮箱、REALITY 伪装站点、监听端口、管理员账号等参数。
- 自动申请并续期 HTTPS 证书，用于管理后端和订阅接口。
- 支持 HTTP-01 或 Cloudflare DNS API 自动签发 HTTPS 证书。
- 提供 Clash Meta 订阅地址，客户端可直接导入。
- Clash Meta 订阅内置本地分流策略，不依赖远程规则集。
- 提供完整 Web 管理后端，用于查看服务状态、管理用户、修改节点参数、查看流量统计、重启 Xray、复制订阅地址。
- 当前 VPS 单节点订阅即可，不做多节点聚合。
- 尽量保持安装脚本幂等，可重复执行、升级、卸载。
- 不提供 Docker 部署模式。

### 域名与证书边界

REALITY 本身不依赖本机域名证书。它需要生成 X25519 私钥/公钥，并配置 `serverNames`、`dest`、`shortIds` 等参数。

本项目中的域名和证书主要用于：

- HTTPS 管理面板，例如 `https://panel.example.com:8443`。
- HTTPS 订阅接口，例如 `https://panel.example.com:8443/sub/<token>/clash.yaml`。
- ACME 自动签发和续期证书。

推荐准备一个独立域名或子域名指向 VPS：

- `panel.example.com`：管理后端和订阅接口。
- Xray REALITY 客户端连接地址默认使用该域名的 DNS 解析结果。

### 端口设计

默认推荐让 Xray REALITY 独占 443，管理面板使用独立 HTTPS 端口，默认 `8443`。这样代理入口和后台入口完全分开，不依赖 Nginx `stream` SNI 分流。

- `0.0.0.0:443`：Xray REALITY 入口。
- `0.0.0.0:8443`：Nginx HTTPS 管理面板和订阅接口。
- `0.0.0.0:80`：Nginx HTTP，负责 ACME HTTP-01 验证和 HTTP 跳转。

这样可以同时满足：

- VLESS REALITY 对外走 443。
- 管理后端和订阅地址使用独立 HTTPS 端口。
- 证书由 Certbot 自动申请和续期。

## 推荐架构

```text
Client
  |
  | 443/tcp
  v
Xray REALITY 0.0.0.0:443

Admin / Subscription
  |
  | 8443/tcp
  v
Nginx HTTPS 0.0.0.0:8443 --> Admin API 127.0.0.1:8080

80/tcp
  |
  `-- Nginx HTTP --> ACME webroot / HTTP redirect
```

### 组件

- Xray Core：VLESS + REALITY 服务端。
- Nginx：HTTP 站点和后台 HTTPS 反代。
- Certbot：Let's Encrypt 证书申请和续期，支持 webroot 和 Cloudflare DNS API。
- Python FastAPI：轻量管理后端和订阅生成 API。
- SQLite：保存用户、订阅 token、节点参数、管理员账号。
- Xray StatsService：按用户读取上传、下载和总流量。
- systemd：托管 `xray`、`proxy-panel`、证书续期 hook。

## 项目规划

```text
.
├── install.sh                    # 一键安装入口
├── uninstall.sh                  # 卸载入口
├── upgrade.sh                    # 升级 Xray / 后端
├── README.md
├── panel/
│   ├── app.py                    # FastAPI 应用入口
│   ├── database.py               # SQLite 初始化和查询
│   ├── security.py               # 密码哈希、JWT、订阅 token
│   ├── xray_config.py            # Xray 配置生成
│   ├── subscriptions.py          # Clash / VLESS 订阅生成
│   ├── requirements.txt
│   └── templates/                # 简单管理页面
├── scripts/
│   ├── common.sh                 # 公共函数、日志、校验
│   ├── install_xray.sh           # 安装 Xray
│   ├── install_nginx.sh          # 安装并配置 Nginx
│   ├── install_cert.sh           # 证书申请和续期
│   ├── install_panel.sh          # 管理后端安装
│   ├── firewall.sh               # UFW 规则
│   └── install_xray.sh           # Xray Core 与 REALITY 密钥
├── templates/
│   ├── nginx.http.conf.tpl
│   ├── nginx.panel-https.conf.tpl
│   └── proxy-panel.service.tpl
└── docs/
    ├── configuration.md
    ├── api.md
    └── troubleshooting.md
```

## 安装流程设计

### 交互式输入

`install.sh` 首次执行时收集以下信息：

- 面板域名：例如 `panel.example.com`。
- ACME 邮箱：用于 Let's Encrypt 证书签发。
- 管理员用户名。
- 管理员密码，留空则自动生成强密码。
- Xray 对外端口，默认 `443`。
- REALITY 监听地址，默认 `0.0.0.0:443`。
- 后台 HTTPS 端口，默认 `8443`。
- REALITY 伪装目标 `dest`，默认 `www.microsoft.com:443`。
- REALITY `serverName`，默认从 `dest` 提取。
- Xray API 本地监听端口，默认 `127.0.0.1:10085`，用于流量统计。
- 证书签发方式：`http` 或 `cloudflare`。
- Cloudflare DNS API Token，选择 `cloudflare` 时必填。
- 节点名称，例如 `vps-reality-01`。
- 是否启用 UFW 防火墙。

### 自动执行步骤

1. 检查系统版本、root 权限、域名解析、端口占用。
2. 安装基础依赖：`curl`、`wget`、`unzip`、`jq`、`openssl`、`nginx`、`certbot`、`python3-venv`。
3. 下载并安装 Xray Core。
4. 生成 REALITY 密钥对、`shortId`、默认用户 UUID。
5. 通过 HTTP-01 或 Cloudflare DNS API 申请 HTTPS 证书。
6. 渲染 Nginx HTTP 和后台 HTTPS 配置，并清理旧版 stream 分流配置。
7. 安装 FastAPI 管理后端和 systemd 服务。
8. 生成 Xray 配置并启动服务。
9. 输出管理后台地址、默认用户、订阅地址、Clash 导入地址。

## Xray 配置约定

默认入站配置：

- 协议：`vless`
- 传输：`tcp`
- 安全：`reality`
- Flow：`xtls-rprx-vision`
- 监听：`0.0.0.0:443`
- 对外入口：`443/tcp`
- StatsService：`127.0.0.1:10085`

示例客户端字段：

```yaml
proxies:
  - name: vps-reality-01
    type: vless
    server: panel.example.com
    port: 443
    uuid: 00000000-0000-0000-0000-000000000000
    network: tcp
    tls: true
    udp: true
    flow: xtls-rprx-vision
    servername: www.microsoft.com
    client-fingerprint: chrome
    reality-opts:
      public-key: XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
      short-id: 0123456789abcdef
```

## 订阅设计

### HTTPS 订阅地址

每个用户拥有独立订阅 token：

```text
https://panel.example.com:8443/sub/<token>/clash.yaml
https://panel.example.com:8443/sub/<token>/vless.txt
```

### Clash Meta 输出

订阅接口生成 Clash Meta 兼容 YAML，包含：

- `proxies`
- `proxy-groups`
- `rules`
- 本地分流规则：局域网、私有地址、本地域名和 `GEOIP,CN` 走 `DIRECT`。
- 强制代理规则：Claude、ChatGPT/OpenAI、Figma 相关域名始终走 `Proxy`，并且优先级高于国内直连规则。
- DNS 防泄漏：启用 `tun.dns-hijack`、`strict-route`、`respect-rules`，强制代理域名使用带 `#Proxy` 的 DoH 解析。
- 兜底策略：未命中的流量走 `Final`，默认选择 `Proxy`。
- 内置 DNS：国内 DoH nameserver、海外 fallback、fake-ip 过滤局域网域名。
- REALITY 必需参数：`servername`、`client-fingerprint`、`reality-opts.public-key`、`reality-opts.short-id`

订阅不使用远程 `rule-providers`，也不使用 `GEOSITE` 规则，避免客户端/Nikki 因下载或解析 `GeoSite.dat` 失败而拒绝配置。客户端导入后即可从订阅服务器获取完整配置。

DNS 防泄漏依赖客户端支持 Mihomo/Clash Meta 的 TUN 与 DNS 配置。若客户端禁用 TUN、系统私有 DNS、浏览器内置 DoH 或平台限制阻止 DNS 劫持，仍可能出现客户端侧 DNS 泄漏，需要在客户端关闭这些外部 DNS 路径。

### 订阅安全

- 订阅 token 使用高强度随机值。
- 订阅接口仅通过 HTTPS 提供。
- 支持重置 token。
- 支持按用户启停订阅。
- 后续可增加访问日志、速率限制和过期时间。

## 管理后端设计

- 登录 / 退出。
- 查看 Xray、Nginx、面板服务状态。
- 查看和编辑当前节点参数。
- 查看每个用户上传、下载、总流量。
- 新增、禁用、删除 VLESS 用户。
- 重置用户 UUID 和订阅 token。
- 生成并复制 Clash 订阅链接。
- 重新生成 Xray 配置并重启 Xray。
- 查看最近安装和服务错误日志摘要。

### 安全策略

- 管理员密码使用 Argon2 或 bcrypt 哈希保存。
- 后台会话使用 HTTP-only cookie。
- 登录失败限速。
- 后台仅暴露在 HTTPS 域名下。
- 默认不开放数据库远程访问。
- systemd 服务使用独立低权限用户运行。

## 配置文件路径

安装完成后的默认路径：

```text
/etc/xray/config.json
/etc/nginx/sites-available/proxy-panel.conf
/opt/proxy-panel/
/var/lib/proxy-panel/panel.db
/var/log/proxy-panel/
/usr/local/bin/proxy-panel
```

## 命令设计

安装：

```bash
bash install.sh
```

管理：

```bash
proxy-panel status
proxy-panel traffic
proxy-panel reset-traffic
proxy-panel add-user <name>
proxy-panel disable-user <name>
proxy-panel reset-token <name>
proxy-panel restart
proxy-panel show-sub <name>
```

卸载：

```bash
bash uninstall.sh
```

## 验收标准

- Ubuntu 22.04 clean VPS 上执行 `bash install.sh` 可以完成部署。
- `systemctl status xray nginx proxy-panel` 均为 running。
- `https://面板域名:8443` 可以打开管理后端。
- Clash Meta 可通过 HTTPS 订阅导入。
- VLESS REALITY 节点可正常连接。
- 管理后台可查看用户上传、下载和总流量。
- Cloudflare DNS API 模式可以在 80 端口受限时签发证书。
- 证书续期后 Nginx 自动 reload。
- 重启 VPS 后服务自动恢复。

## 后续实现里程碑

### Milestone 1：脚本骨架

- 初始化项目结构。
- 编写 `common.sh`。
- 实现系统检测、依赖安装、日志输出。

### Milestone 2：Xray 部署

- 安装 Xray Core。
- 生成 REALITY 密钥、UUID、shortId。
- 渲染 `/etc/xray/config.json`。
- 配置 systemd。

### Milestone 3：HTTPS 与分流

- 配置 Nginx HTTP 和后台 HTTPS。
- 使用 Certbot 申请证书。
- 配置证书续期 hook。

### Milestone 4：管理后端

- 实现 FastAPI 后端。
- 实现 SQLite 数据层。
- 实现登录、用户管理、节点设置、服务状态、流量统计。

### Milestone 5：订阅生成

- 生成 Clash Meta YAML。
- 生成 VLESS 分享链接。
- 实现订阅 token 管理。

### Milestone 6：打磨与测试

- 在 Ubuntu 22.04 clean VPS 验证。
- 增加卸载、升级和故障诊断文档。
- 补充常见客户端导入说明。

## 已确认范围

- 管理后端提供完整 Web UI。
- 当前 VPS 单节点订阅即可，不做多节点聚合。
- 支持按用户查看流量统计。
- 支持 Cloudflare DNS API 自动签发证书。
- 不提供 Docker 部署模式。
