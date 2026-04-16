# 中国航班实时雷达

基于 ADS-B 数据的中国空域实时航班追踪器。

## 快速启动

```bash
pip install flask flask-cors requests
python app.py
```

访问 http://localhost:5000

## 数据来源

- [OpenSky Network](https://opensky-network.org) — 全球 ADS-B 数据（免费匿名访问）
- 全球请求后后端过滤中国空域（N15-55, E70-140）
- 10秒缓存，15秒前端自动刷新

## 功能

- 实时显示中国空域航班（约500-600架）
- 飞机图标按航向旋转，按高度着色（红=高空/黄=中空/绿=低空/灰=地面）
- 点击飞机查看详情（呼号、ICAO24、国籍、高度、速度、航向、垂直速率）
- 统计面板：按国家/高度分布
- 暗色地图主题（CartoDB Dark Matter）

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /api/flights` | 中国空域实时航班数据 |
| `GET /api/flight/<icao24>` | 单架航班详情 |
| `GET /api/stats` | 统计信息 |

## 技术栈

- 后端：Flask + requests
- 前端：Leaflet.js + 暗色主题
- 数据：OpenSky Network ADS-B API
