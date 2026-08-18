param(
  [string]$Chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$reportDir = Join-Path $root 'reports\images-mobile-viewport'
$shotDir = Join-Path $reportDir 'screenshots'
New-Item -ItemType Directory -Force -Path $shotDir | Out-Null
$pagePath = '/school/110041107-%EA%B2%BD%EB%8F%99%EA%B3%A0%EB%93%B1%ED%95%99%EA%B5%90/%EC%98%81%EC%96%B4%EA%B3%BC%EC%99%B8/'

function Receive-Cdp($socket, [int]$wantedId) {
  $buffer = New-Object byte[] 1048576
  while ($true) {
    $segment = [ArraySegment[byte]]::new($buffer)
    $stream = New-Object System.IO.MemoryStream
    do {
      $result = $socket.ReceiveAsync($segment, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
      $stream.Write($buffer, 0, $result.Count)
    } while (-not $result.EndOfMessage)
    $json = [Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
    if ($null -ne $json.id -and [int]$json.id -eq $wantedId) { return $json }
  }
}

function Send-Cdp($socket, [ref]$nextId, [string]$method, $params) {
  $id = $nextId.Value
  $nextId.Value++
  $payload = @{id=$id; method=$method; params=$params} | ConvertTo-Json -Compress -Depth 12
  $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
  $socket.SendAsync([ArraySegment[byte]]::new($bytes), [Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).GetAwaiter().GetResult() | Out-Null
  return Receive-Cdp $socket $id
}

function Capture-Set([string]$name, [int]$port, [int]$debugPort) {
  $profile = Join-Path $env:TEMP "studyway-cdp-$debugPort"
  if (Test-Path -LiteralPath $profile) { Remove-Item -LiteralPath $profile -Recurse -Force }
  $url = "http://127.0.0.1:$port$pagePath"
  $proc = Start-Process -FilePath $Chrome -ArgumentList @('--headless=new',"--remote-debugging-port=$debugPort","--user-data-dir=$profile",'--no-first-run','--disable-gpu','--hide-scrollbars',$url) -WindowStyle Hidden -PassThru
  try {
    $targets = $null
    for ($i=0; $i -lt 50 -and $null -eq $targets; $i++) {
      Start-Sleep -Milliseconds 200
      try { $targets = Invoke-RestMethod "http://127.0.0.1:$debugPort/json" } catch {}
    }
    $target = $targets | Where-Object { $_.type -eq 'page' -and $_.url -like "*$pagePath*" } | Select-Object -First 1
    if ($null -eq $target) { throw "CDP page target not found for $name" }
    $socket = [Net.WebSockets.ClientWebSocket]::new()
    $socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
    $nextId = 1
    Send-Cdp $socket ([ref]$nextId) 'Page.enable' @{} | Out-Null
    $rows = @()
    foreach ($width in @(320,390,430)) {
      Send-Cdp $socket ([ref]$nextId) 'Emulation.setDeviceMetricsOverride' @{width=$width;height=1400;deviceScaleFactor=1;mobile=$true;screenWidth=$width;screenHeight=1400} | Out-Null
      Send-Cdp $socket ([ref]$nextId) 'Page.reload' @{ignoreCache=$true} | Out-Null
      Start-Sleep -Milliseconds 900
      $expr = @'
(() => {
 const img=document.querySelector('.content-image-sequence img');
 const seq=document.querySelector('.content-image-sequence');
 const article=document.querySelector('article');
 const r=img.getBoundingClientRect(), a=article.getBoundingClientRect();
 const cs=getComputedStyle(article);
 return {viewport:innerWidth,imageRenderedWidth:r.width,leftGap:r.left,rightGap:innerWidth-r.right,
   containerWidth:a.width,articlePaddingLeft:parseFloat(cs.paddingLeft),articlePaddingRight:parseFloat(cs.paddingRight),
   horizontalOverflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),
   crop:(img.naturalWidth/img.naturalHeight)-(r.width/r.height),imageCount:seq.querySelectorAll('img').length};
})()
'@
      $eval = Send-Cdp $socket ([ref]$nextId) 'Runtime.evaluate' @{expression=$expr;returnByValue=$true}
      $shot = Send-Cdp $socket ([ref]$nextId) 'Page.captureScreenshot' @{format='png';fromSurface=$true;captureBeyondViewport=$false}
      $file = Join-Path $shotDir "$name-$width.png"
      [IO.File]::WriteAllBytes($file, [Convert]::FromBase64String($shot.result.data))
      $rows += $eval.result.result.value
    }
    $socket.Dispose()
    return $rows
  } finally {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
  }
}

$result = [ordered]@{
  page = $pagePath
  existing = @(Capture-Set 'existing-mobile-wide' 8900 9231)
  candidate = @(Capture-Set 'new-mobile-viewport' 8901 9232)
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $reportDir 'chrome-responsive-audit.json') -Encoding UTF8
$result | ConvertTo-Json -Depth 8
