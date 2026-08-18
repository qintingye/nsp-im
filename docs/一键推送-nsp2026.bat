@echo off
REM ============================================
REM 一键推送：公网密码统一为 nsp2026
REM ============================================

echo ============================================
echo  Step 1: 克隆 GitHub 仓库
echo ============================================
cd /d D:\
if exist nsp-im-public (
    echo 仓库已存在, 直接 pull...
    cd nsp-im-public
    git pull origin main
) else (
    git clone https://github.com/qintingye/nsp-im.git nsp-im-public
    cd nsp-im-public
)

echo.
echo ============================================
echo  Step 2: 备份旧版 + 复制 d5 覆盖 index.html
echo ============================================
if exist index.html (
    copy /Y index.html index.html.bak.%date:~0,4%%date:~5,2%%date:~8,2% >nul
    echo 已备份旧版 index.html
)
copy /Y "D:\Obsidian-Knowledge\01-Domain\新型电力系统建设\政策框架\六网协同\14-六网协同可视化-d5.html" index.html
echo 已复制 d5 到 index.html

echo.
echo ============================================
echo  Step 3: 复制 PWA 资源（如果存在）
echo ============================================
if exist "D:\Obsidian-Knowledge\01-Domain\新型电力系统建设\政策框架\六网协同\manifest.json" (
    copy /Y "D:\Obsidian-Knowledge\01-Domain\新型电力系统建设\政策框架\六网协同\manifest.json" manifest.json >nul
    echo manifest.json 已更新
) else (
    echo manifest.json 不存在, 跳过
)
if exist "D:\Obsidian-Knowledge\01-Domain\新型电力系统建设\政策框架\六网协同\sw.js" (
    copy /Y "D:\Obsidian-Knowledge\01-Domain\新型电力系统建设\政策框架\六网协同\sw.js" sw.js >nul
    echo sw.js 已更新
) else (
    echo sw.js 不存在, 跳过
)

echo.
echo ============================================
echo  Step 4: 提交 + 推送
echo ============================================
git add -A
git commit -m "fix: 升级 W3-D5 (95KB) - 密码 nsp2026 - 7 Tab"
git push origin main

if errorlevel 1 (
    echo.
    echo ============================================
    echo  推送失败! 请检查:
    echo  1. gh auth status (是否已登录)
    echo  2. 网络连接
    echo  3. 仓库权限
    echo ============================================
    pause
    exit /b 1
)

echo.
echo ============================================
echo  推送成功!
echo  等 1-2 分钟后访问:
echo  https://qintingye.github.io/nsp-im/
echo  密码: nsp2026
echo ============================================

pause