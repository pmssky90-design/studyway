param(
  [string]$Chrome='C:\Program Files\Google\Chrome\Application\chrome.exe',
  [int]$Port=8774,
  [int]$ReferencePort=8773
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$out=Join-Path $root 'reports\home-design\chrome'
New-Item -ItemType Directory -Force $out|Out-Null

function Recv($ws,[int]$want){$buf=New-Object byte[] 1048576;while($true){$seg=[ArraySegment[byte]]::new($buf);$ms=New-Object IO.MemoryStream;do{$r=$ws.ReceiveAsync($seg,[Threading.CancellationToken]::None).GetAwaiter().GetResult();$ms.Write($buf,0,$r.Count)}while(-not $r.EndOfMessage);$j=[Text.Encoding]::UTF8.GetString($ms.ToArray())|ConvertFrom-Json;if($null-ne$j.id-and[int]$j.id-eq$want){return $j}}}
function Cmd($ws,[ref]$n,[string]$method,$params){$id=$n.Value;$n.Value++;$s=@{id=$id;method=$method;params=$params}|ConvertTo-Json -Compress -Depth 10;$b=[Text.Encoding]::UTF8.GetBytes($s);$ws.SendAsync([ArraySegment[byte]]::new($b),[Net.WebSockets.WebSocketMessageType]::Text,$true,[Threading.CancellationToken]::None).GetAwaiter().GetResult()|Out-Null;Recv $ws $id}

$http=@{}
foreach($path in @('/','/static/css/site.css','/assets/images/home/studyway-main-hero.png')){$r=Invoke-WebRequest -Uri ("http://127.0.0.1:$Port"+$path) -UseBasicParsing;$http[$path]=[int]$r.StatusCode}
$profile=Join-Path $env:TEMP 'studyway-home-design-9434';if(Test-Path $profile){Remove-Item $profile -Recurse -Force}
$proc=Start-Process $Chrome -ArgumentList @('--headless=new','--remote-debugging-port=9434',"--user-data-dir=$profile",'--no-first-run','--disable-gpu','--hide-scrollbars',"http://127.0.0.1:$Port/") -WindowStyle Hidden -PassThru
try{
  $targets=$null;for($i=0;$i-lt50-and$null-eq$targets;$i++){Start-Sleep -Milliseconds 200;try{$targets=Invoke-RestMethod 'http://127.0.0.1:9434/json'}catch{}}
  $target=$targets|Where-Object{$_.type-eq'page'}|Select-Object -First 1
  $ws=[Net.WebSockets.ClientWebSocket]::new();$ws.ConnectAsync([Uri]$target.webSocketDebuggerUrl,[Threading.CancellationToken]::None).GetAwaiter().GetResult()
  $n=1;Cmd $ws ([ref]$n) 'Page.enable' @{}|Out-Null
  $expr=@'
(()=>{const hero=document.querySelector('.home-hero img'),intro=document.querySelector('.home-intro'),regions=document.querySelector('#regions'),schools=document.querySelector('#schools'),header=document.querySelector('header'),main=document.querySelector('main'),active=document.querySelector('.school-area-panel.is-active'),hr=hero?.getBoundingClientRect(),hs=hero?getComputedStyle(hero):null,regionLinks=[...document.querySelectorAll('#regions .link-grid a')],schoolLinks=[...(active||schools||document).querySelectorAll('a')],order=[header,hero?.closest('section'),intro,regions,schools].filter(Boolean);return{title:document.title,h1:document.querySelectorAll('h1').length,hero:!!hero,heroNatural:[hero?.naturalWidth,hero?.naturalHeight],heroRect:[hr?.width,hr?.height],heroRatioError:hr?Math.abs(hr.width/hr.height-1.5):999,heroObjectFit:hs?.objectFit,heroClipped:!!(hr&&(hr.left<0||hr.right>innerWidth)),intro:!!intro,regions:!!regions,schools:!!schools,orderPass:order.length===5&&order.every((x,i)=>i===0||!!(order[i-1].compareDocumentPosition(x)&Node.DOCUMENT_POSITION_FOLLOWING)),documentOverflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),mainOverflow:main?Math.max(0,main.scrollWidth-main.clientWidth):999,introClipped:intro?intro.scrollWidth>intro.clientWidth||intro.scrollHeight>intro.clientHeight:true,regionCardClipped:regionLinks.filter(x=>x.scrollWidth>x.clientWidth||x.scrollHeight>x.clientHeight).length,schoolLinkClipped:schoolLinks.filter(x=>x.offsetParent!==null&&(x.scrollWidth>x.clientWidth||x.scrollHeight>x.clientHeight)).length,regionColumns:regions?getComputedStyle(regions.querySelector('.link-grid')).gridTemplateColumns.split(' ').length:0,schoolColumns:active?getComputedStyle(active.querySelector('.school-link-grid')).gridTemplateColumns.split(' ').length:0,heroLoaded:hero?.complete&&hero?.naturalWidth===1536&&hero?.naturalHeight===1024,cssLoaded:[...document.styleSheets].some(x=>x.href&&x.href.endsWith('/static/css/site.css'))}})()
'@
  $responsive=@()
  foreach($width in @(1920,1440,768,430,412,390,375,360,320)){
    Cmd $ws ([ref]$n) 'Emulation.setDeviceMetricsOverride' @{width=$width;height=1000;deviceScaleFactor=1;mobile=($width-lt768);screenWidth=$width;screenHeight=1000}|Out-Null
    Cmd $ws ([ref]$n) 'Page.navigate' @{url=("http://127.0.0.1:$Port/")}|Out-Null;Start-Sleep -Milliseconds 800
    $e=Cmd $ws ([ref]$n) 'Runtime.evaluate' @{expression=$expr;returnByValue=$true};$v=$e.result.result.value;$v|Add-Member width $width;$responsive+=$v
    if($width-eq390-or$width-eq1440){$shot=Cmd $ws ([ref]$n) 'Page.captureScreenshot' @{format='png';fromSurface=$true;captureBeyondViewport=$true};[IO.File]::WriteAllBytes((Join-Path $out "home-$width.png"),[Convert]::FromBase64String($shot.result.data))}
  }
  $contentPath='/region/%EA%B0%95%EB%82%A8%EA%B5%AC/all/%EA%B3%BC%EC%99%B8/'
  $styleExpr=@'
(()=>{const pick=s=>{const e=document.querySelector(s);if(!e)return null;const c=getComputedStyle(e);return{display:c.display,width:c.width,padding:c.padding,margin:c.margin,color:c.color,background:c.backgroundColor,fontSize:c.fontSize,lineHeight:c.lineHeight,border:c.border,borderRadius:c.borderRadius}};return{bodyClass:document.body.className,body:pick('body'),main:pick('main'),content:pick('.content-body-card'),heading:pick('.content-body-card h2'),reviews:pick('.excel-review-section'),related:pick('.related-navigation')}})()
'@
  $styles=@{}
  foreach($p in @($ReferencePort,$Port)){
    Cmd $ws ([ref]$n) 'Emulation.setDeviceMetricsOverride' @{width=1440;height=1000;deviceScaleFactor=1;mobile=$false;screenWidth=1440;screenHeight=1000}|Out-Null
    Cmd $ws ([ref]$n) 'Page.navigate' @{url=("http://127.0.0.1:$p"+$contentPath)}|Out-Null;Start-Sleep -Milliseconds 700
    $e=Cmd $ws ([ref]$n) 'Runtime.evaluate' @{expression=$styleExpr;returnByValue=$true};$styles["$p"]=$e.result.result.value
  }
  $styleEqual=(ConvertTo-Json $styles["$ReferencePort"] -Compress -Depth 8)-eq(ConvertTo-Json $styles["$Port"] -Compress -Depth 8)
  $result=@{chrome='Google Chrome';http=$http;responsive=$responsive;content_page=$contentPath;content_computed_style_equal=$styleEqual;content_styles=$styles}
  $result|ConvertTo-Json -Depth 10|Set-Content (Join-Path $out 'validation.json') -Encoding UTF8
  $result|ConvertTo-Json -Depth 10
  $ws.Dispose()
}finally{if($proc-and-not$proc.HasExited){Stop-Process $proc.Id -Force}}
