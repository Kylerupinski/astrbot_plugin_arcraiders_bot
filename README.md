# astrbot_plugin_arcraiders_bot

> [AstrBot](https://github.com/AstrBotDevs/AstrBot) 上的 Arc Raiders 查询插件，当前仅支持地图事件查询。数据来源于 [MetaForge](https://metaforge.app/arc-raiders)。


| 指令 | 说明 |
|------|------|
| `/arc get` | 手动拉取最新事件数据及图标 |
| `/arc map` | 查询当前及下一时段各地图事件 |

## 计划功能

- 🗸图片输出
- □订阅指定地图事件推送
- □远征倒计时/远征窗口期剩余时间

## 配置

在 AstrBot 插件管理面板中可设置：

- `plain_text_output` — 纯文本输出开关（默认关闭）。

## 功能特性

- 自动获取 Arc Raiders 地图事件时间表
- 按北京时间过滤当前时段与下一时段事件
- 地图名、事件名中英翻译
- 纯文本/图片双模式输出
- 图片模式下自动加载事件图标，横版双栏布局

## 相关链接

- [AstrBot 仓库](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
- [MetaForge Arc Raiders](https://metaforge.app/arc-raiders)
