# 微信小程序图标说明

## 需要的图标文件

您需要在 `miniprogram/images/` 目录下放置以下图标文件：

| 文件名称 | 尺寸 | 用途 |
|---------|------|------|
| monitor.png | 48x48px | 监控页面图标（未选中） |
| monitor-active.png | 48x48px | 监控页面图标（选中） |
| call.png | 48x48px | 呼叫页面图标（未选中） |
| call-active.png | 48x48px | 呼叫页面图标（选中） |

## 获取图标的方法

### 方法1：使用在线图标生成器
1. 访问 https://www.iconfont.cn/
2. 搜索"监控"、"呼叫"等关键词
3. 下载 PNG 格式图标，尺寸选择 48x48px

### 方法2：使用简单的纯色图标
创建简单的 PNG 图标文件，使用不同颜色区分选中和未选中状态：
- 未选中：灰色 (#888888)
- 选中：主题色 (#667eea)

### 方法3：暂时移除 tabBar
如果暂时没有图标，可以先注释掉 `app.json` 中的 tabBar 配置，使用页面跳转方式。

## 目录结构

```
miniprogram/
├── images/
│   ├── monitor.png
│   ├── monitor-active.png
│   ├── call.png
│   └── call-active.png
├── pages/
│   ├── index/
│   │   ├── index.js
│   │   ├── index.wxml
│   │   └── index.wxss
│   └── elevator/
│       ├── elevator.js
│       ├── elevator.wxml
│       └── elevator.wxss
├── app.js
├── app.json
├── app.wxss
└── sitemap.json
```

## 注意事项

1. 图标必须是 PNG 格式
2. 图标尺寸建议为 48x48px 或 64x64px
3. 图标文件命名必须与 `app.json` 中的配置一致
4. 选中和未选中图标需要成对出现

---

## 开发完成后

1. 在微信开发者工具中打开项目
2. 配置小程序 AppID
3. 预览和调试
4. 提交审核发布

完成后用户即可扫码使用！ 🎉