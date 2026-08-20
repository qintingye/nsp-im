# NSP-IM v3.0 · CloudBase 自动同步指南

## 配置步骤
1. 进入 CloudBase 控制台
2. 选择 liuwang-jiankong-d2eatyj479b1861-1471069936 环境
3. 云函数 → 创建函数
4. 函数名: auto-sync
5. 运行时: Python 3.11
6. 内存: 256MB
7. 超时: 120 秒
8. 上传 cloudfunctions/auto-sync/ 目录
9. 触发器 → 创建
10. Cron: */30 * * * * (每 30 分钟)
11. 启用
