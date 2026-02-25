# 后台启动竞品监控
$action = New-ScheduledTaskAction -Execute "pythonw" -Argument "d:\coding\jpfx\main.py --schedule"
$trigger = New-ScheduledTaskTrigger -Daily -At 17:00
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName "竞品监控日报" -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "任务已创建，每天17:00自动运行"
