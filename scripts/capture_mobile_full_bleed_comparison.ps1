param([string]$Chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe')

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$reportDir = Join-Path $root 'reports\images-mobile-full-bleed'
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
  $id = $nextId.Value; $nextId.Value++
  $payload = @{id=$id;method=$method;params=$params} | ConvertTo-Json -Compress -Depth 12
  $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
  $socket.SendAsync([ArraySegment[byte]]::new($bytes),[Net.WebSockets.WebSocketMessageType]::Text,$true,[Threading.CancellationToken]::None).GetAwaiter().GetResult() | Out-Null
  Receive-Cdp $socket $id
}

function Capture-Set([string]$name,[int]$port,[int]$debugPort,[int[]]$widths) {
  $profile = Join-Path $env:TEMP "studyway-full-bleed-cdp-$debugPort"
  if (Test-Path -LiteralPath $profile) { Remove-Item -LiteralPath $profile -Recurse -Force }
  $url = "http://127.0.0.1:$port$pagePath"
  $proc = Start-Process -FilePath $Chrome -ArgumentList @('--headless=new',"--remote-debugging-port=$debugPort","--user-data-dir=$profile",'--no-first-run','--disable-gpu','--hide-scrollbars',$url) -WindowStyle Hidden -PassThru
  try {
    $targets=$null
    for($i=0;$i -lt 50 -and $null -eq $targets;$i++){Start-Sleep -Milliseconds 200;try{$targets=Invoke-RestMethod "http://127.0.0.1:$debugPort/json"}catch{}}
    $target=$targets|Where-Object{$_.type -eq 'page' -and $_.url -like "*$pagePath*"}|Select-Object -First 1
    if($null -eq $target){throw "CDP target not found: $name"}
    $socket=[Net.WebSockets.ClientWebSocket]::new();$socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl,[Threading.CancellationToken]::None).GetAwaiter().GetResult()
    $nextId=1;Send-Cdp $socket ([ref]$nextId) 'Page.enable' @{}|Out-Null;$rows=@()
    foreach($width in $widths){
      Send-Cdp $socket ([ref]$nextId) 'Emulation.setDeviceMetricsOverride' @{width=$width;height=1400;deviceScaleFactor=1;mobile=$true;screenWidth=$width;screenHeight=1400}|Out-Null
      Send-Cdp $socket ([ref]$nextId) 'Page.reload' @{ignoreCache=$true}|Out-Null;Start-Sleep -Milliseconds 900
      $expr=@'
(()=>{const img=document.querySelector('.content-image-sequence img'),seq=document.querySelector('.content-image-sequence'),article=document.querySelector('article'),h1=document.querySelector('h1'),r=img.getBoundingClientRect(),s=seq.getBoundingClientRect(),a=article.getBoundingClientRect(),cs=getComputedStyle(article),imgs=[...seq.querySelectorAll('img')];return{viewport:innerWidth,imageWidth:r.width,imageLeft:r.left,imageRight:r.right,sequenceWidth:s.width,containerWidth:a.width,articlePaddingLeft:parseFloat(cs.paddingLeft),articlePaddingRight:parseFloat(cs.paddingRight),horizontalOverflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),crop:Math.abs((img.naturalWidth/img.naturalHeight)-(r.width/r.height)),imageCount:imgs.length,imageGapMax:Math.max(0,...imgs.slice(1).map((x,i)=>x.getBoundingClientRect().top-imgs[i].getBoundingClientRect().bottom)),h1Width:h1.getBoundingClientRect().width}})()
'@
      $eval=Send-Cdp $socket ([ref]$nextId) 'Runtime.evaluate' @{expression=$expr;returnByValue=$true}
      $shot=Send-Cdp $socket ([ref]$nextId) 'Page.captureScreenshot' @{format='png';fromSurface=$true;captureBeyondViewport=$false}
      [IO.File]::WriteAllBytes((Join-Path $shotDir "$name-$width.png"),[Convert]::FromBase64String($shot.result.data))
      $rows+=$eval.result.result.value
    }
    $socket.Dispose();$rows
  }finally{if(-not $proc.HasExited){Stop-Process -Id $proc.Id -Force}}
}

$result=[ordered]@{
  page=$pagePath
  fullBleed=@(Capture-Set 'full-bleed' 8902 9240 @(320,360,375,390,412,430))
  comparison8900=@(Capture-Set 'candidate-8900' 8900 9241 @(390))
  comparison8901=@(Capture-Set 'candidate-8901' 8901 9242 @(390))
}
$result|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $reportDir 'chrome-full-bleed-audit.json') -Encoding UTF8
$result|ConvertTo-Json -Depth 8
