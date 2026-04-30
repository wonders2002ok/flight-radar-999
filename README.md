# 中国航班实时雷达

基于 ADS-B 数据的中国空域实时航班追踪器，数据来源 FlightRadar24。

## 快速启动

```bash
pip install flask flask-cors FlightRadar24API
python app.py
```

访问 http://localhost:5000

## 数据来源

- [FlightRadar24](https://www.flightradar24.com) — 全球实时 ADS-B/MLAT 数据（通过非官方 API）
- 边界框直接过滤中国空域（N15-55, E70-140）
- 8秒后端缓存，10秒前端自动刷新

## 功能

- 实时显示中国空域航班（约500-600架）
- 飞机图标按航向旋转，按高度着色（红=高空/黄=中空/绿=低空/灰=地面）
- 点击飞机查看详情（呼号、ICAO24、航司/机型、高度、速度、航向、垂直速率、Squawk 紧急告警）
- 航班搜索：按呼号快速定位
- 紧急代码告警：7700/7600/7500 高亮提示
- 统计面板：按航司/高度分布
- 暗色地图主题（CartoDB Dark Matter）

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /api/flights` | 中国空域实时航班数据 |
| `GET /api/flight/<icao24>` | 单架航班详情 |
| `GET /api/stats` | 统计信息 |
| `GET /api/airline_map` | 航司 IATA → 名称映射 |
| `GET /api/aircraft_map` | 机型代码 → 名称映射 |

## 技术栈

- 后端：Flask + FlightRadar24API
- 前端：Leaflet.js + 暗色主题
- 数据：FlightRadar24（非官方 API）
