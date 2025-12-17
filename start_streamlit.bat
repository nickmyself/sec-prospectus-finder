@echo off
pushd "%~dp0"
powershell -NoProfile -NoExit -Command "& {
	$scriptPath = '%~dp0'
	$pythonCmd = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1).Source
	if (-not $pythonCmd) { $pythonCmd = (Get-Command py -ErrorAction SilentlyContinue | Select-Object -First 1).Source }
	if (-not $pythonCmd) { Write-Output 'ERROR: python or py not found in PATH'; exit 1 }
	$log = Join-Path $scriptPath 'streamlit.log'
	$appPath = Join-Path $scriptPath 'app.py'
	$p = Start-Process -FilePath $pythonCmd -ArgumentList '-m','streamlit','run',$appPath,'--server.port','8501' -PassThru -RedirectStandardOutput $log -RedirectStandardError $log
	$p.Id | Out-File -FilePath (Join-Path $scriptPath 'streamlit.pid') -Encoding ASCII
	Write-Output ('Started Streamlit PID=' + $p.Id)
	# wait for port to be listening (max 30s)
	$max = 30; $i = 0
	while ($i -lt $max) {
		if (Test-NetConnection -ComputerName 'localhost' -Port 8501 -InformationLevel Quiet) {
			Start-Process 'http://localhost:8501'
			break
		}
		Start-Sleep -Seconds 1
		$i++
	}
	if ($i -ge $max) { Write-Output 'Timeout waiting for server (30s). Check streamlit.log in the app folder.' }
}"
popd
