$env:NO_PROXY = "localhost,127.0.0.1,::1"
$env:no_proxy = "localhost,127.0.0.1,::1"
$env:GRADIO_ANALYTICS_ENABLED = "False"

& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\local_app.py" --host 127.0.0.1 --port 8808 --device auto --concurrency 2 --queue-size 16
