# 中国航班实时雷达 — 技术文档

> **版本**: v2.0 | **日期**: 2026-04-29 | **分支**: main

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [后端技术细节](#3-后端技术细节)
4. [前端技术细节](#4-前端技术细节)
5. [数据流与刷新机制](#5-数据流与刷新机制)
6. [API 接口规范](#6-api-接口规范)
7. [部署与运维](#7-部署与运维)
8. [演进历史](#8-演进历史)
9. [文件结构](#9-文件结构)
10. [已知局限与改进方向](#10-已知局限与改进方向)

---

## 1. 项目概述

**中国航班实时雷达** 是一个基于 Web 的中国空域实时航班追踪可视化系统。它从 FlightRadar24 非官方 API 获取实时 ADS-B 飞行数据，使用 Leaflet.js 在暗色地图上以可旋转的飞机图标展示航班位置、高度、速度和航向等信息。

### 核心能力

| 能力 | 描述 |
|------|------|
| 实时追踪 | 显示中国空域（N15°–55°, E70°–140°）内所有配备 ADS-B 应答机的航班，通常 500–600 架 |
| 可视化编码 | 飞机图标按航向旋转，按高度着色（红=高空 / 黄=中空 / 绿=低空 / 灰=地面） |
| 交互查询 | 点击任意飞机弹出详情面板：呼号、ICAO24、国籍、高度、地速、航向、垂直速率、Squawk 码 |
| 统计面板 | 实时在线/空中航班计数、按国籍 Top 10 分布、按高度分层统计 |
| 自动刷新 | 前端每 10 秒自动拉取数据，后端 8 秒缓存窗口防止 API 限流 |

### 技术栈一览

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | Flask（Python） | 最新 |
| 跨域支持 | flask-cors | 最新 |
| 数据源 SDK | FlightRadar24API（PyPI） | 最新 |
| 前端地图 | Leaflet.js | 1.9.4 |
| 地图瓦片 | CartoDB Dark Matter（CDN） | — |
| 运行时 | Python 3.x | — |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     用户浏览器                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              index.html (SPA)                         │  │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │  │
│  │  │ Leaflet  │  │ plane     │  │  auto-refresh    │  │  │
│  │  │ 地图渲染  │  │ SVG 图标  │  │  timer (10s)     │  │  │
│  │  └──────────┘  └───────────┘  └──────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │  HTTP GET /api/flights           │
└──────────────────────────┼──────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                    Flask Server (port 5000)                 │
│  ┌───────────────────────┴──────────────────────────────┐  │
│  │                   app.py                              │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌──────────────┐ │  │
│  │  │ CORS       │  │ fetch_       │  │ in-memory    │ │  │
│  │  │ middleware  │  │ flights_data │  │ cache (8s)   │ │  │
│  │  └────────────┘  └──────┬───────┘  └──────────────┘ │  │
│  └──────────────────────────┼────────────────────────────┘  │
│                             │                               │
│  ┌──────────────────────────┼────────────────────────────┐  │
│  │            FlightRadar24API SDK                       │  │
│  │  · fr_api.get_bounds()  → 定义地理矩形               │  │
│  │  · fr_api.get_flights() → 获取航班列表               │  │
│  └──────────────────────────┼────────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────┘
                               │  HTTPS (非官方 API)
┌──────────────────────────────┼──────────────────────────────┐
│                 FlightRadar24 服务器                        │
│            (全球实时 ADS-B / MLAT 数据聚合)                 │
└─────────────────────────────────────────────────────────────┘
```

### 架构特征

- **单体应用**：后端和前端打包在同一进程，Flask 同时托管 API 和静态页面
- **无状态**：服务器端仅保留内存缓存，无数据库，无持久化
- **拉模型**：前端定时轮询（pull），不是 WebSocket 推送
- **纯客户端渲染**：所有 UI 逻辑在浏览器端通过原生 JavaScript 执行

---

## 3. 后端技术细节

### 3.1 启动与编码修复（app.py:7–10）

```python
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
```

- **目的**：Windows 中文环境下默认终端编码为 GBK，可能导致 UTF-8 字符（emoji 等）输出时报 `UnicodeEncodeError`
- **做法**：将 stdout/stderr 重新包装为 UTF-8 编码，用 `replace` 策略静默替换无法编码的字符

### 3.2 地理边界（app.py:28–33）

```python
CHINA_BOUNDS = {
    "lamin": 15.0,   # 南海诸岛 — 南界
    "lamax": 55.0,   # 东北边境 — 北界
    "lomin": 70.0,   # 西部边境 — 西界
    "lomax": 140.0,  # 东海     — 东界
}
```

- **坐标系**：WGS84（EPSG:4326）
- **覆盖范围**：包含中国大陆全境、台湾、南海诸岛、部分中亚和东北亚空域
- **FR24 API 映射**：`tl_y`=北, `tl_x`=西, `br_y`=南, `br_x`=东（top-left / bottom-right 矩形）

### 3.3 缓存策略（app.py:36–45）

```python
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 8  # 秒
```

| 参数 | 值 | 原因 |
|------|-----|------|
| TTL | 8 秒 | 略短于前端 10 秒轮询间隔，确保每次前端请求大概率命中缓存而不触发外部 API |
| 缓存范围 | 全量数据 | 不仅缓存 `/api/flights`，`/api/stats` 和 `/api/flight/<id>` 也复用同一缓存 |
| 降级策略 | 返回过期缓存 | API 异常时如果有旧缓存则返回旧数据，避免前端断流 |

**缓存命中流程**：

```
请求 → now - timestamp < 8s? → YES → 直接返回 _cache["data"]
                              → NO  → 调用 FR24 API → 更新 _cache → 返回
```

### 3.4 数据获取与单位转换（app.py:39–103）

#### API 调用链

```
fr_api.get_bounds(tl_y, tl_x, br_y, br_x) → bounds 对象
fr_api.get_flights(bounds=bounds)         → Flight 对象列表
```

`FlightRadar24API.get_bounds()` 返回一个 bounds 对象，其内部结构为 `{tl_y, tl_x, br_y, br_x}`，对应地图的经纬度矩形。

#### 原始数据字段

| FR24 Flight 属性 | 含义 | 原始单位 |
|------------------|------|----------|
| `icao_24bit` | ICAO 24 位飞机地址 | — |
| `callsign` | 航班呼号 | — |
| `airline_iata` | 航空公司 IATA 代码 | — |
| `latitude` / `longitude` | WGS84 坐标 | 度 |
| `altitude` | 气压高度 | 英尺 (feet) |
| `ground_speed` | 地速 | 节 (knots) |
| `heading` | 真航向 | 度 (0–360) |
| `vertical_speed` | 垂直速率 | 英尺/分钟 (fpm) |
| `on_ground` | 地面/空中标志 | 布尔 |
| `squawk` | 应答机编码 | 4 位八进制 |
| `aircraft_code` | 机型代码（如 B738） | 字符串 |

#### 单位转换公式

| 目标字段 | 公式 | 系数 | 精度 |
|----------|------|------|------|
| `baro_altitude` (m) | feet × 0.3048 | 0.3048 | 1 位小数 |
| `velocity` (km/h) | knots × 1.852 | 1.852 | 1 位小数 |
| `vertical_rate` (m/s) | fpm × 0.00508 | 0.00508 | 1 位小数 |

#### 输出数据结构

```json
{
  "time": 1714400000,
  "count": 523,
  "flights": [
    {
      "icao24": "780a1b",
      "callsign": "CES5123",
      "origin_country": "MU",
      "longitude": 116.4074,
      "latitude": 39.9042,
      "baro_altitude": 10668.0,
      "on_ground": false,
      "velocity": 850.2,
      "true_track": 45,
      "vertical_rate": 5.1,
      "geo_altitude": 10668.0,
      "squawk": "1000",
      "emergency": null,
      "category": "B738"
    }
  ]
}
```

### 3.5 路由设计

| 路由 | 方法 | 处理函数 | 功能 |
|------|------|----------|------|
| `/` | GET | `index()` | 读取并返回 `index.html` |
| `/api/flights` | GET | `get_flights()` | 返回全量缓存航班数据（JSON） |
| `/api/flight/<icao24>` | GET | `get_flight(icao24)` | 按 ICAO24 查找单架航班 |
| `/api/stats` | GET | `get_stats()` | 返回聚合统计信息 |
| `/api/airline_map` | GET | `airline_map()` | 返回航司 IATA 代码 → 名称/国家映射 |
| `/api/aircraft_map` | GET | `aircraft_map()` | 返回机型代码 → 名称/制造商映射 |

### 3.6 统计计算（/api/stats）

#### 国籍分布

遍历所有航班，按 `origin_country`（实际为航司 IATA 代码）分组计数，取 Top 10。

```python
countries[country] = countries.get(country, 0) + 1
top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]
```

#### 高度分层

| 分类 | 条件 | 含义 |
|------|------|------|
| 地面 | `on_ground == True` 或 `altitude is None` | 停机/滑行 |
| 低空 (<3000m) | `altitude < 3000` | 起飞/进近 |
| 中空 (3000–8000m) | `3000 ≤ altitude < 8000` | 爬升/下降 |
| 高空 (8000–12000m) | `8000 ≤ altitude < 12000` | 巡航 |
| 超高 (>12000m) | `altitude ≥ 12000` | 远程巡航 |

### 3.7 服务器配置

```python
app.run(host="0.0.0.0", port=5000, debug=False)
```

- `host="0.0.0.0"`：绑定所有网络接口，允许局域网内其他设备访问
- `port=5000`：Flask 默认端口
- `debug=False`：生产模式（无热重载，无调试器）

---

## 4. 前端技术细节

### 4.1 地图初始化（index.html:350–364）

```javascript
const map = L.map('map', {
    center: [35.0, 105.0],  // 中国地理中心（甘肃兰州附近）
    zoom: 5,                // 初始缩放级别（可视中国全境）
    minZoom: 3,
    maxZoom: 12,
});
```

**瓦片源**：CartoDB Dark Matter (`cartocdn.com`)

- 暗色主题与航空雷达仪表风格一致
- 无需 API Key，通过 CDN 免费使用
- 4 个子域名（`a,b,c,d`）并行加载，提升瓦片加载速度

### 4.2 飞机图标系统

#### SVG 飞机形状（index.html:369–371）

```svg
<path d="M12 2 L14 8 L22 11 L14 13 L14 18 L17 20 L14 21 L12 22 L10 21 L7 20 L10 18 L10 13 L2 11 L10 8 Z"
      transform="rotate(heading, 12, 12)"/>
```

- 坐标系：24×24 viewBox，旋转中心 (12, 12) 即机身中心
- SVG `<path>` 绘制上单翼喷气客机轮廓，含机身、机翼、尾翼
- 缩放和旋转通过 Leaflet `L.divIcon` 的 CSS transform 实现

#### 高度着色映射（index.html:382–387）

```
高度范围           颜色        色值      语义
─────────────────────────────────────────────
> 10000 m         红色        #ff6b6b    远程巡航
3000–10000 m      黄色        #ffd93d    爬升/下降/短程巡航
< 3000 m          绿色        #6bcb77    起飞/进近
地面/未知         灰色        #6b7b8d    停机/滑行
```

- 阈值 3000m ≈ FL100, 10000m ≈ FL330，与民航过渡高度/巡航高度对齐
- 着色同时应用于地图图标和详情面板高度值

### 4.3 标记管理（index.html:418–465）

#### 增量更新算法

```
1. 创建空集合 newIcaos
2. 遍历新航班数据：
   ├── 将 icao24 加入 newIcaos
   ├── 如果 markers[icao24] 已存在 → 更新位置 (setLatLng) + 图标 (setIcon)
   └── 如果不存在             → 创建新 marker，绑定 click 事件
3. 遍历现有 markers：
   └── 如果 icao24 不在 newIcaos → 从地图移除该 marker 并删除
```

- **时间复杂度**：O(n)，每轮全量刷新而非增量 patch
- **内存占用**：每个 marker 约保持一个 Leaflet 对象 + 一份 flightData 副本
- **事件绑定**：每个 marker 的 `click` 事件调用 `showDetail(f)`，`f` 为内嵌的 `flightData` 引用

### 4.4 自动刷新策略（index.html:525–528）

```javascript
const AUTO_REFRESH_INTERVAL = 10000;  // 10 秒
autoRefreshTimer = setInterval(refreshData, AUTO_REFRESH_INTERVAL);
```

| 参数 | 值 | 说明 |
|------|-----|------|
| 刷新间隔 | 10 秒 | 前端轮询周期 |
| 后端缓存 | 8 秒 | 一个刷新周期内后端最多打 1–2 次外部 API |
| 外部 API 最小间隔 | 8 秒 | 防止 FR24 限流/封禁 |
| 总外部 API 请求频率 | ≤ 7.5 次/分钟 | 实际远低于此值 |

### 4.5 跨域处理（index.html:406）

```javascript
const apiBase = window.location.port === '5500' ? 'http://127.0.0.1:5000' : '';
```

- **场景**：使用 VS Code Live Server（默认端口 5500）开发时，自动将 API 请求指向 Flask 后端（端口 5000）
- **生产模式**：如果从 Flask 的 `/` 路由加载页面，端口即 5000，`apiBase` 为空字符串，使用相对路径

### 4.6 详情面板（index.html:468–498）

显示字段：ICAO24、呼号、国籍/航司代码、高度（带颜色编码）、地速、航向、垂直速率（含升降箭头）、经纬度、Squawk 码（条件渲染）。

### 4.7 加载与反馈 UI

| 组件 | 触发条件 | 行为 |
|------|----------|------|
| 加载遮罩 | 页面首次加载 | 旋转动画 + "正在连接 ADS-B 数据源..." 文字，数据返回后 0.5s 淡出 |
| Toast 通知 | 数据刷新成功/失败 | 底部居中 3 秒自动消失 |
| 刷新按钮 | 手动点击 | 按钮变灰 + "⏳ 加载中..."，请求完成后恢复 |

---

## 5. 数据流与刷新机制

### 完整数据流时序

```
时间轴 →
────────────────────────────────────────────────────────────
T=0s    前端 init() → fetch(/api/flights) → 后端
T=0s    后端 缓存未命中 → fr_api.get_flights() → FR24 服务器
T=~1s   后端 收到数据 → 单位转换 → 缓存 → JSON 响应 → 前端
T=~1s   前端 renderFlights() → 创建 markers → 隐藏 loading
T=1s    前端 startAutoRefresh() → setInterval(10s)
T=10s   前端 refreshData() → fetch(/api/flights) → 后端
         后端 缓存命中(未过期) → 直接返回缓存 JSON → 前端
         前端 renderFlights() → 增量更新 markers
T=18s   后端 缓存过期(>8s) → 再次调用 FR24 API
...
```

### 缓存窗口与外部请求频率

```
前端轮询:  |--10s--|--10s--|--10s--|--10s--|
后端缓存:  |---8s---| 过期 |---8s---| 过期 |
外部API:   ↑调用          ↑调用
```

每 10 秒最多 1 次外部 API 调用（6 次/分钟），远低于 FR24 的限流阈值。

---

## 6. API 接口规范

### 6.1 GET /api/flights

**响应**：

```json
{
  "time": 1714400000,
  "count": 523,
  "flights": [
    {
      "icao24": "780a1b",
      "callsign": "CES5123",
      "origin_country": "MU",
      "longitude": 116.4074,
      "latitude": 39.9042,
      "baro_altitude": 10668.0,
      "on_ground": false,
      "velocity": 850.2,
      "true_track": 45,
      "vertical_rate": 5.1,
      "geo_altitude": 10668.0,
      "squawk": "1000",
      "category": "B738"
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `time` | int | Unix 时间戳 | 数据获取时间 |
| `count` | int | 架 | 航班总数 |
| `flights[].icao24` | string | — | ICAO 24 位飞机地址（小写 hex） |
| `flights[].callsign` | string | — | 航班呼号，无数据时为 "N/A" |
| `flights[].origin_country` | string | — | 航司 IATA 代码，无数据时为 "未知" |
| `flights[].longitude` | float | 度 | WGS84 经度（4 位小数） |
| `flights[].latitude` | float | 度 | WGS84 纬度（4 位小数） |
| `flights[].baro_altitude` | float\|null | 米 | 气压高度（1 位小数），地面/无数据时为 null |
| `flights[].on_ground` | bool | — | 是否在地面 |
| `flights[].velocity` | float\|null | km/h | 地速（1 位小数） |
| `flights[].true_track` | float | 度 | 真航向 0–360，无数据时为 0 |
| `flights[].vertical_rate` | float\|null | m/s | 垂直速率（1 位小数），正值上升 |
| `flights[].geo_altitude` | float\|null | 米 | 几何高度，当前等同于 baro_altitude |
| `flights[].squawk` | string\|null | — | 应答机编码 |
| `flights[].emergency` | string\|null | — | 紧急代码（"7700"/"7600"/"7500"），非紧急时为 null |
| `flights[].category` | string | — | 机型代码（如 B738、A320） |

### 6.2 GET /api/flight/:icao24

**路径参数**：`icao24` — ICAO 24 位飞机地址（大小写不敏感）

**成功响应**（200）：
```json
{
  "icao24": "780a1b",
  "callsign": "CES5123",
  ...
}
```

**失败响应**（404）：
```json
{ "error": "航班未找到" }
```

### 6.3 GET /api/stats

**响应**：

```json
{
  "total": 523,
  "top_countries": [
    { "country": "MU", "count": 85 },
    { "country": "CZ", "count": 72 }
  ],
  "altitude_ranges": {
    "地面": 45,
    "低空(<3000m)": 38,
    "中空(3000-8000m)": 120,
    "高空(8000-12000m)": 280,
    "超高(>12000m)": 40
  },
  "cache_age": 2.3
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | int | 航班总数 |
| `top_countries` | array | 按航班数降序 Top 10 航司 IATA |
| `altitude_ranges` | object | 5 个高度分层的航班计数 |
| `cache_age` | float | 当前缓存已存续秒数 |

### 6.4 GET /api/airline_map

**响应**：

```json
{
  "CCA": {"name": "中国国际航空", "country": "中国"},
  "CES": {"name": "中国东方航空", "country": "中国"}
}
```

返回航司 IATA 代码到中文名称及注册国家的静态映射表，数据来自 `airline_map.json`。

### 6.5 GET /api/aircraft_map

**响应**：

```json
{
  "B738": {"name": "波音 737-800", "mfr": "Boeing", "type": "窄体客机"},
  "A320": {"name": "空客 A320", "mfr": "Airbus", "type": "窄体客机"}
}
```

返回机型 ICAO 代码到名称、制造商、宽窄体分类的静态映射表，数据来自 `aircraft_map.json`。

---

## 7. 部署与运维

### 7.1 依赖安装

```bash
pip install flask flask-cors FlightRadar24API
```

### 7.2 启动方式

#### 方式一：命令行

```bash
python app.py
# 访问 http://localhost:5000
```

#### 方式二：Windows 批处理脚本（`start_radar.bat`）

```
脚本流程：
1. 切换到脚本所在目录
2. 检查 FlightRadar24 库是否已安装，未安装则自动 pip install
3. 在新 cmd 窗口中启动 python app.py
4. 等待 3 秒（让 Flask 完成初始化）
5. 自动打开默认浏览器访问 http://localhost:5000
```

### 7.3 网络要求

- **出站**：需要访问 `data-live.flightradar24.com`（FR24 非官方 API 端点，由 SDK 封装）
- **入站**：TCP 5000 端口（如果从局域网其他设备访问）
- **CDN**：需要访问 `unpkg.com`（Leaflet JS/CSS）和 `cartocdn.com`（地图瓦片）

### 7.4 故障处理

| 症状 | 可能原因 | 解决方案 |
|------|----------|----------|
| 前端一直显示 loading | Flask 未启动或端口冲突 | 检查 `python app.py` 是否正常运行，确认 5000 端口未被占用 |
| 地图显示但无航班 | FR24 API 限流或网络问题 | 等待几分钟重试；检查是否能访问 FR24 网站 |
| 前端不自动刷新 | JavaScript 被浏览器拦截 | 检查浏览器控制台错误；部分浏览器插件可能阻止定时器 |
| Unicode 乱码 | Windows GBK 编码问题 | 已通过 stdout 重包装修复（app.py:7–10） |
| pip 安装 FlightRadar24API 失败 | Python 版本不兼容 | 确保 Python ≥ 3.8 |

---

## 8. 演进历史

| 提交 | 日期 | 内容 |
|------|------|------|
| `0b4cfc3` | 2026-04-16 | **初始版本**：基于 OpenSky Network ADS-B API |
| `bb376ed` | 2026-04-16 | Initial commit（合并） |
| `48285b2` | 2026-04-16 | 解决 README 冲突 |
| `b474775` | 2026-04-24 | **重大升级**：数据源从 OpenSky 切换为 FlightRadar24 API；新增 `start_radar.bat` 一键启动脚本；优化刷新间隔（10s 前端 / 8s 后端缓存） |

### 数据源迁移

| 维度 | OpenSky（v1.0） | FlightRadar24（v2.0） |
|------|-----------------|----------------------|
| API 端点 | `opensky-network.org/api` | `FlightRadar24API`（SDK 封装） |
| 数据丰富度 | 基础（icao24, callsign, 位置, 高度, 速度） | 丰富（增加航向, 垂直速率, squawk, 机型, 航司代码, 地面标志） |
| 请求方式 | HTTP REST，全球请求后手动过滤中国空域 | SDK 封装，边界框参数直接过滤 |
| 速率限制 | 匿名用户约 10 秒/次 | 未公开，8 秒缓存保守访问 |

---

## 9. 文件结构

```
flight-radar-999/
├── .git/
├── .gitignore              # 排除 __pycache__, .env, venv, *.db, *.pyc
├── LICENSE                 # MIT License
├── README.md               # 项目说明
├── app.py                  # Flask 后端主程序
├── index.html              # 前端单页应用
├── start_radar.bat         # Windows 一键启动脚本
├── airline_map.json        # 航司 IATA → 名称/国家映射表
├── aircraft_map.json       # 机型代码 → 名称/制造商映射表
├── TECHNICAL_DOCUMENTATION.md  # 本文档
└── IMPROVEMENT_RECOMMENDATIONS.md  # 改进建议（行业横向对比）
```

### 代码量统计

| 文件 | 语言 | 职责 |
|------|------|------|
| `app.py` | Python | API 服务、数据获取、缓存、单位转换、紧急代码检测 |
| `index.html` | HTML/CSS/JS | 地图渲染、标记管理、详情面板、统计 UI、搜索/告警 |
| `start_radar.bat` | Batch | 依赖检查、服务启动、浏览器打开 |
| `airline_map.json` | JSON | 42 条航司 IATA 映射 |
| `aircraft_map.json` | JSON | 100+ 条机型代码映射 |

---

## 10. 已知局限与改进方向

### 当前局限

| 局限 | 影响 | 严重程度 |
|------|------|----------|
| **单点缓存** | 缓存仅存于内存，多进程部署时各实例独立请求 FR24 API | 中 |
| **无历史数据** | 不存储任何航班轨迹历史，无法回放或分析趋势 | 中 |
| **无客户端过滤** | 600+ 架航班全部渲染到 DOM，低性能设备可能卡顿 | 低 |
| **无认证机制** | API 完全开放，公网部署可能被滥用 | 中 |
| **前端轮询模式** | 10 秒内航班位置不更新，不够平滑 | 低 |
| **`origin_country` 语义不清** | 实际存的是航司 IATA 代码（如 "MU"），不是国家名 | 低 |
| **无 WebSocket 推送** | 无法实现真正的实时更新 | 中 |

### 建议改进方向

1. **WebSocket 实时推送**：用 Flask-SocketIO 或迁移至 FastAPI + WebSocket，替代前端轮询
2. **Redis 缓存层**：将内存缓存外移至 Redis，支持多进程/多实例部署
3. **时序数据库**：接入 InfluxDB 或 TimescaleDB 存储航班轨迹，支持历史回放
4. **航班轨迹线**：前端绘制每架飞机的历史轨迹 polyline（需配合数据存储）
5. **地图聚合**：高缩放级别时使用 Leaflet.markercluster 减少 DOM 节点
6. **API 鉴权**：添加简单的 API Key 或 Token 验证
7. **Docker 化**：编写 Dockerfile + docker-compose，简化跨平台部署
8. **语义修正**：将 `origin_country` 重命名为 `airline_code`，从航司 IATA 查表获取真实国家名

---

> **文档生成**: 由 Claude Code 基于源码与 Git 历史生成，2026-04-29
