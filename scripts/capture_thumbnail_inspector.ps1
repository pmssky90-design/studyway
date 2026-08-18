param([string]$Chrome='C:\Program Files\Google\Chrome\Application\chrome.exe')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$out=Join-Path $root 'reports\thumbnail-preview'
function Recv($ws,[int]$want){$buf=New-Object byte[] 1048576;while($true){$seg=[ArraySegment[byte]]::new($buf);$ms=New-Object IO.MemoryStream;do{$r=$ws.ReceiveAsync($seg,[Threading.CancellationToken]::None).GetAwaiter().GetResult();$ms.Write($buf,0,$r.Count)}while(-not $r.EndOfMessage);$j=[Text.Encoding]::UTF8.GetString($ms.ToArray())|ConvertFrom-Json;if($null-ne$j.id-and[int]$j.id-eq$want){return $j}}}
function Cmd($ws,[ref]$n,[string]$method,$params){$id=$n.Value;$n.Value++;$s=@{id=$id;method=$method;params=$params}|ConvertTo-Json -Compress -Depth 10;$b=[Text.Encoding]::UTF8.GetBytes($s);$ws.SendAsync([ArraySegment[byte]]::new($b),[Net.WebSockets.WebSocketMessageType]::Text,$true,[Threading.CancellationToken]::None).GetAwaiter().GetResult()|Out-Null;Recv $ws $id}
$profile=Join-Path $env:TEMP 'studyway-thumbnail-inspector-9411';if(Test-Path $profile){Remove-Item $profile -Recurse -Force}
$proc=Start-Process $Chrome -ArgumentList @('--headless=new','--remote-debugging-port=9411',"--user-data-dir=$profile",'--no-first-run','--disable-gpu','--hide-scrollbars','--window-size=1440,1200','http://127.0.0.1:8910/') -WindowStyle Hidden -PassThru
try{
  $targets=$null;for($i=0;$i-lt50-and$null-eq$targets;$i++){Start-Sleep -Milliseconds 200;try{$targets=Invoke-RestMethod 'http://127.0.0.1:9411/json'}catch{}}
  $target=$targets|Where-Object{$_.type-eq'page'-and$_.url-like'*8910*'}|Select-Object -First 1
  $ws=[Net.WebSockets.ClientWebSocket]::new();$ws.ConnectAsync([Uri]$target.webSocketDebuggerUrl,[Threading.CancellationToken]::None).GetAwaiter().GetResult();$n=1
  Cmd $ws ([ref]$n) 'Page.enable' @{}|Out-Null
  Start-Sleep -Seconds 3
  $before=(Cmd $ws ([ref]$n) 'Runtime.evaluate' @{expression="(()=>({title:document.title,total:document.querySelector('#total')?.textContent,normal:document.querySelector('#normal')?.textContent,errors:document.querySelector('#errors')?.textContent,thumbs:document.querySelectorAll('#thumbs .thumb').length,cards:document.querySelectorAll('#results .card').length}))()";returnByValue=$true}).result.result.value
  $search=(Cmd $ws ([ref]$n) 'Runtime.evaluate' @{expression="(()=>{const q=document.querySelector('#query');q.value='/region/';q.dispatchEvent(new Event('input',{bubbles:true}));return{cards:document.querySelectorAll('#results .card').length,first:document.querySelector('#results .card h3')?.textContent}})()";returnByValue=$true}).result.result.value
  $random=(Cmd $ws ([ref]$n) 'Runtime.evaluate' @{expression="(()=>{document.querySelector('#random').click();return{cards:document.querySelectorAll('#results .card').length}})()";returnByValue=$true}).result.result.value
  $shot=Cmd $ws ([ref]$n) 'Page.captureScreenshot' @{format='png';fromSurface=$true;captureBeyondViewport=$false}
  [IO.File]::WriteAllBytes((Join-Path $out 'inspector-screenshot.png'),[Convert]::FromBase64String($shot.result.data))
  $result=@{before=$before;search=$search;random=$random;httpUrl='http://127.0.0.1:8910/'}
  $result|ConvertTo-Json -Depth 6|Set-Content (Join-Path $out 'chrome-validation.json') -Encoding UTF8
  $result|ConvertTo-Json -Depth 6
  $ws.Dispose()
}finally{if($proc-and-not$proc.HasExited){Stop-Process $proc.Id -Force}}
