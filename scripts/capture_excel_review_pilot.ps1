param(
  [string]$Chrome='C:\Program Files\Google\Chrome\Application\chrome.exe',
  [int]$Port=8772,
  [string]$ReportRelative='reports\excel-review-pilot\chrome',
  [string]$PagesRelative='reports\excel-review-pilot\pages.json'
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$out=Join-Path $root $ReportRelative
New-Item -ItemType Directory -Force $out|Out-Null

function Recv($ws,[int]$want){$buf=New-Object byte[] 1048576;while($true){$seg=[ArraySegment[byte]]::new($buf);$ms=New-Object IO.MemoryStream;do{$r=$ws.ReceiveAsync($seg,[Threading.CancellationToken]::None).GetAwaiter().GetResult();$ms.Write($buf,0,$r.Count)}while(-not $r.EndOfMessage);$j=[Text.Encoding]::UTF8.GetString($ms.ToArray())|ConvertFrom-Json;if($null -ne $j.id -and [int]$j.id -eq $want){return $j}}}
function Cmd($ws,[ref]$n,[string]$method,$params){$id=$n.Value;$n.Value++;$s=@{id=$id;method=$method;params=$params}|ConvertTo-Json -Compress -Depth 10;$b=[Text.Encoding]::UTF8.GetBytes($s);$ws.SendAsync([ArraySegment[byte]]::new($b),[Net.WebSockets.WebSocketMessageType]::Text,$true,[Threading.CancellationToken]::None).GetAwaiter().GetResult()|Out-Null;Recv $ws $id}

$pages=Get-Content (Join-Path $root $PagesRelative) -Raw -Encoding UTF8|ConvertFrom-Json
$paths=@()
$paths+=@($pages|Where-Object{$_.page_type-eq'region_content'-and$_.subject-eq'math'}|Select-Object -First 4 -ExpandProperty url)
$paths+=@($pages|Where-Object{$_.page_type-eq'region_content'-and$_.subject-eq'english'}|Select-Object -First 4 -ExpandProperty url)
$paths+=@($pages|Where-Object{$_.page_type-eq'region_content'-and$_.subject-eq'general'}|Select-Object -First 4 -ExpandProperty url)
$paths+=@($pages|Where-Object{$_.page_type-eq'school_content'-and$_.subject-eq'math'}|Select-Object -First 4 -ExpandProperty url)
$paths+=@($pages|Where-Object{$_.page_type-eq'school_content'-and$_.subject-eq'english'}|Select-Object -First 4 -ExpandProperty url)

$http=@();foreach($path in $paths){$r=Invoke-WebRequest -Uri ("http://127.0.0.1:$Port"+$path) -UseBasicParsing;$http+=@{url=$path;status=[int]$r.StatusCode}}
$profile=Join-Path $env:TEMP 'studyway-excel-review-9422';if(Test-Path $profile){Remove-Item $profile -Recurse -Force}
$proc=Start-Process $Chrome -ArgumentList @('--headless=new','--remote-debugging-port=9422',"--user-data-dir=$profile",'--no-first-run','--disable-gpu','--hide-scrollbars',"http://127.0.0.1:$Port/") -WindowStyle Hidden -PassThru
try{
  $targets=$null;for($i=0;$i-lt50-and$null-eq$targets;$i++){Start-Sleep -Milliseconds 200;try{$targets=Invoke-RestMethod 'http://127.0.0.1:9422/json'}catch{}}
  $target=$targets|Where-Object{$_.type-eq'page'}|Select-Object -First 1
  $ws=[Net.WebSockets.ClientWebSocket]::new();$ws.ConnectAsync([Uri]$target.webSocketDebuggerUrl,[Threading.CancellationToken]::None).GetAwaiter().GetResult()
  $n=1;Cmd $ws ([ref]$n) 'Page.enable' @{}|Out-Null;$responsive=@();$representatives=@()
  $expr=@'
(()=>{const s=document.querySelector('.excel-review-section'),g=document.querySelector('.excel-review-grid'),cs=[...document.querySelectorAll('.excel-review-card')],ts=[...document.querySelectorAll('.excel-review-card h3')],body=document.querySelector('.content-body-card'),related=document.querySelector('.related-navigation'),st=s?getComputedStyle(s):null,r=s?s.getBoundingClientRect():null,gr=g?g.getBoundingClientRect():null,last=cs.at(-1)?.getBoundingClientRect(),h2=body?.querySelector('h2'),h2s=h2?getComputedStyle(h2):null;return{url:location.pathname,statusTitle:document.title,section:!!s,cards:cs.length,columns:g?getComputedStyle(g).gridTemplateColumns.split(' ').length:0,overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),cardOverflow:cs.filter(x=>x.scrollWidth>x.clientWidth).length,titleClipping:ts.filter(x=>x.scrollWidth>x.clientWidth||x.scrollHeight>x.clientHeight).length,stars:document.querySelectorAll('.excel-review-stars').length,reviewSchema:[...document.querySelectorAll('script[type="application/ld+json"]')].filter(x=>/Review|AggregateRating|ratingValue|reviewCount|bestRating|worstRating/.test(x.textContent)).length,display:st?.display,visibility:st?.visibility,opacity:st?.opacity,height:st?.height,maxHeight:st?.maxHeight,wrapperOverflow:st?.overflow,position:st?.position,computedWidth:r?.width,computedHeight:r?.height,visible:!!(r&&r.width>0&&r.height>0&&st.display!=='none'&&st.visibility!=='hidden'&&st.opacity!=='0'),afterContentBody:!!(body&&s&&(body.compareDocumentPosition(s)&Node.DOCUMENT_POSITION_FOLLOWING)),beforeRelated:!!(related&&s&&(s.compareDocumentPosition(related)&Node.DOCUMENT_POSITION_FOLLOWING)),siteCssLoaded:[...document.styleSheets].some(x=>x.href&&x.href.endsWith('/static/css/site.css')),fifthCentered:!!(gr&&last&&Math.abs((last.left+last.width/2)-(gr.left+gr.width/2))<1),bodyH2Styled:!!(h2s&&h2s.borderTopWidth!=='0px'&&h2s.backgroundColor!=='rgba(0, 0, 0, 0)')}})()
'@
  foreach($width in @(1920,1440,430,412,390,375,360,320)){
    Cmd $ws ([ref]$n) 'Emulation.setDeviceMetricsOverride' @{width=$width;height=1000;deviceScaleFactor=1;mobile=($width-lt768);screenWidth=$width;screenHeight=1000}|Out-Null
    Cmd $ws ([ref]$n) 'Page.navigate' @{url=("http://127.0.0.1:$Port"+$paths[0])}|Out-Null;Start-Sleep -Milliseconds 650
    Cmd $ws ([ref]$n) 'Runtime.evaluate' @{expression="document.querySelector('.excel-review-section').scrollIntoView()"}|Out-Null
    $e=Cmd $ws ([ref]$n) 'Runtime.evaluate' @{expression=$expr;returnByValue=$true};$v=$e.result.result.value;$v|Add-Member width $width;$responsive+=$v
    $shot=Cmd $ws ([ref]$n) 'Page.captureScreenshot' @{format='png';fromSurface=$true;captureBeyondViewport=$false};[IO.File]::WriteAllBytes((Join-Path $out "review-$width.png"),[Convert]::FromBase64String($shot.result.data))
    if($width -eq 390 -or $width -eq 1440){$full=Cmd $ws ([ref]$n) 'Page.captureScreenshot' @{format='png';fromSurface=$true;captureBeyondViewport=$true};[IO.File]::WriteAllBytes((Join-Path $out "full-page-$width.png"),[Convert]::FromBase64String($full.result.data))}
  }
  foreach($path in $paths){
    Cmd $ws ([ref]$n) 'Emulation.setDeviceMetricsOverride' @{width=390;height=1000;deviceScaleFactor=1;mobile=$true;screenWidth=390;screenHeight=1000}|Out-Null
    Cmd $ws ([ref]$n) 'Page.navigate' @{url=("http://127.0.0.1:$Port"+$path)}|Out-Null;Start-Sleep -Milliseconds 500
    $e=Cmd $ws ([ref]$n) 'Runtime.evaluate' @{expression=$expr;returnByValue=$true};$representatives+=$e.result.result.value
  }
  $cssHttp=Invoke-WebRequest -Uri "http://127.0.0.1:$Port/static/css/site.css" -UseBasicParsing
  $result=@{chrome='Google Chrome';representative_count=$paths.Count;css_http=[int]$cssHttp.StatusCode;http=$http;responsive=$responsive;representatives=$representatives}
  $result|ConvertTo-Json -Depth 8|Set-Content (Join-Path $out 'validation.json') -Encoding UTF8
  $result|ConvertTo-Json -Depth 8
  $ws.Dispose()
}finally{if($proc-and-not$proc.HasExited){Stop-Process $proc.Id -Force}}
