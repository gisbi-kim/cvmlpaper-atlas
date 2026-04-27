# step2_s2.py watchdog — 죽으면 자동 재시작
$dir = 'C:\Users\gsk\OneDrive\#. Claude\cvml-paper-atlas'
$log = "$dir\step2_s2.log"
$errlog = "$dir\step2_s2_err.log"

while ($true) {
    Write-Host "$(Get-Date -Format 'HH:mm:ss') Starting step2_s2.py..."
    $proc = Start-Process python -ArgumentList '-u','step2_s2.py' `
        -WorkingDirectory $dir `
        -RedirectStandardOutput $log `
        -RedirectStandardError $errlog `
        -WindowStyle Hidden -PassThru

    Write-Host "PID: $($proc.Id)"
    $proc.WaitForExit()
    $code = $proc.ExitCode
    Write-Host "$(Get-Date -Format 'HH:mm:ss') Exited with code $code"

    # 정상 완료 (exit 0) 또는 로그에 DONE 있으면 종료
    $done = Select-String -Path $log -Pattern '=== DONE ===' -Quiet -ErrorAction SilentlyContinue
    if ($code -eq 0 -and $done) {
        Write-Host "step2_s2 DONE. Exiting watchdog."
        break
    }

    Write-Host "Restarting in 10s..."
    Start-Sleep 10
}
