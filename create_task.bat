@echo off
chcp 65001
schtasks /create /tn "竞品监控日报" /tr "pythonw d:\coding\jpfx\main.py" /sc daily /st 17:00 /f
echo 任务已创建
pause
