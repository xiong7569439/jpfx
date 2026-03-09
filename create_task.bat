@echo off
echo 创建竞品监控日报计划任务...

schtasks /create /tn "竞品监控日报" /tr "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -Command cd d:\coding\jpfx; python main.py" /sc daily /st 17:00 /f

if %errorlevel% == 0 (
    echo 计划任务创建成功！
    echo 每天 17:00 将自动运行竞品监控日报
) else (
    echo 创建失败，错误码: %errorlevel%
)

pause
