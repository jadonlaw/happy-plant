(function(){
  // Happy Plant app. DISPLAY ONLY: every number, word, mood and color comes from the backend.
  var root=document.documentElement;
  function $(id){return document.getElementById(id)}
  function read(k){try{return localStorage.getItem(k)}catch(e){return null}}
  function write(k,v){try{localStorage.setItem(k,v)}catch(e){}}
  function setText(el,t){if(el&&el.textContent!==t)el.textContent=t}
  function show(el,on){if(!el)return;if(el instanceof SVGElement){if(on)el.removeAttribute('hidden');else el.setAttribute('hidden','')}else if(el.hidden===on)el.hidden=!on}
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}

  var S=null;try{S=JSON.parse($('hp-state').textContent)}catch(e){S=null}
  var cur=0,TZ='';try{TZ=Intl.DateTimeFormat().resolvedOptions().timeZone||''}catch(e){}

  // ---------- talking to the backend ----------
  function csrf(){var m=document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);return m?decodeURIComponent(m[1]):''}
  function api(path,data){
    var opt={method:data===undefined?'GET':'POST',credentials:'same-origin',cache:'no-store',
      headers:{'X-TZ':TZ,'X-CSRFToken':csrf()}};
    if(data!==undefined){opt.headers['Content-Type']='application/json';opt.body=JSON.stringify(data)}
    return fetch(path,opt).then(function(r){return r.json().catch(function(){return {ok:false,message:'Something went wrong. Try again.'}}).then(function(d){d._status=r.status;return d})})
      .catch(function(){return {ok:false,_status:0,message:'Can\'t reach Happy Plant. Check your internet.'}})}
  function useState(d){if(d&&d.plants){S=d;renderAll()}}
  function refresh(){if(!S)return Promise.resolve();return api('/api/app/state').then(function(d){if(d.ok)useState(d);else if(d._status===401){S=null;showAuth(true)}})}

  // ---------- theme (a look preference for this phone only) ----------
  var hint=$('themeHint');
  function applyTheme(t){if(t==='system')root.removeAttribute('data-theme');else root.setAttribute('data-theme',t);
    document.querySelectorAll('[data-theme-pick]').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.themePick===t))});
    hint.textContent=t==='system'?'Following your phone':(t==='dark'?'Always dark':'Always light');write('hp.theme',t)}
  applyTheme(read('hp.theme')||'dark');
  document.querySelectorAll('[data-theme-pick]').forEach(function(b){b.addEventListener('click',function(){applyTheme(b.dataset.themePick)})});

  // ---------- settings that live on the backend ----------
  var UNIT_MAP={auto:'A',f:'F',c:'C'};
  document.querySelectorAll('[data-unit]').forEach(function(b){b.addEventListener('click',function(){
    api('/api/app/settings',{temp_unit:UNIT_MAP[b.dataset.unit]}).then(function(d){if(d.ok){HCACHE={};useState(d)}})})});
  [['swPush','push_alerts'],['swDaily','daily_checkin']].forEach(function(x){var s=$(x[0]);s.addEventListener('click',function(){
    var on=s.getAttribute('aria-checked')!=='true',o={};o[x[1]]=on;s.setAttribute('aria-checked',String(on));
    api('/api/app/settings',o).then(function(d){if(d.ok)useState(d)})})});
  function locate(){return new Promise(function(res,rej){if(!navigator.geolocation)return rej();
    navigator.geolocation.getCurrentPosition(function(p){res({lat:p.coords.latitude,lon:p.coords.longitude})},function(){rej()},{timeout:15000,maximumAge:600000})})}
  $('locBtn').addEventListener('click',function(){var s=$('locS');
    locate().then(function(c){return api('/api/app/settings',c)}).then(function(d){if(d.ok){useState(d)}else setText(s,d.message)})
      .catch(function(){setText(s,'Location is off. Allow location for this site in your phone settings, then try again.')})});
  function renderSettings(){if(!S)return;var st=S.settings;
    var key={A:'auto',F:'f',C:'c'}[st.temp_unit];document.querySelectorAll('[data-unit]').forEach(function(x){x.setAttribute('aria-pressed',String(x.dataset.unit===key))});
    $('swPush').setAttribute('aria-checked',String(st.push_alerts));$('swDaily').setAttribute('aria-checked',String(st.daily_checkin));
    setText($('locS'),st.has_location?'Set from your phone. Tap to update.':'Not set yet. Used for night mode and sunrise.');
    setText($('acctEmail'),S.user.email);setText($('plantCount'),S.plant_count);setText($('devCount'),S.device_count)}

  // ---------- navigation ----------
  function go(id){
    document.querySelectorAll('.screen').forEach(function(s){s.classList.toggle('active',s.id===id)});
    var hl=(id==='plants'||id==='devices'||id==='pro')?'settings':id;document.querySelectorAll('.homerow [data-go]').forEach(function(b){if(b.dataset.go===hl)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});
    document.querySelector('.screen.active').scrollTop=0;
    if(id==='history')renderHistory();
  }
  document.querySelectorAll('[data-go]').forEach(function(b){b.addEventListener('click',function(){go(b.dataset.go)})});

  // =========================== HOME ===========================
  function plants(){return S&&S.plants?S.plants:[]}
  function P(){var ps=plants();if(cur>=ps.length)cur=Math.max(0,ps.length-1);return ps[cur]}
  var cardKeys='';
  function render(){
    var ps=plants(),sw0=$('swipe'),eh=$('emptyHome');
    if(!ps.length){show(sw0,false);show(eh,true);document.querySelectorAll('.logo').forEach(function(l){l.classList.remove('mid','sad')});return}
    show(sw0,true);show(eh,false);
    var p=P(),m=p.mood;
    var av=$('heroPhoto');if(p.photo){if(av.getAttribute('src')!==p.photo)av.setAttribute('src',p.photo);show(av,true)}else show(av,false);
    show($('nightPill'),p.night.on);setText($('nightTx'),p.night.text);
    show($('zzz'),m.asleep);show($('eyesOpen'),!m.asleep);show($('eyesShut'),m.asleep);
    setText($('plantName'),p.name);setText($('plantSub'),p.sub);
    setText($('moodWord'),m.word);setText($('moodLine'),m.line);
    var mo=$('mouth');if(mo.getAttribute('d')!==m.mouth)mo.setAttribute('d',m.mouth);
    ['face','moodWord'].forEach(function(id){var e=$(id);['mid','sad','night','fresh'].forEach(function(c){e.classList.toggle(c,c===m.cls)})});
    document.querySelectorAll('.logo').forEach(function(l){['mid','sad'].forEach(function(c){l.classList.toggle(c,c===m.logo)})});
    renderCards(p);
    setText($('waterT'),p.water);
    var st=$('stalePill');show(st,!!p.stale);setText(st,p.stale);
    var dots=$('dots');if(dots.dataset.sig!==ps.length+':'+cur){dots.dataset.sig=ps.length+':'+cur;dots.innerHTML='';ps.forEach(function(_,i){var e=document.createElement('i');if(i===cur)e.className='on';dots.appendChild(e)})}
  }
  function renderCards(p){
    var g=$('readings'),keys=p.cards.map(function(c){return c.k}).join(',');
    if(keys!==cardKeys){cardKeys=keys;g.innerHTML='';g.classList.toggle('three',p.cards.length===3);
      p.cards.forEach(function(c){var b=document.createElement('button');b.type='button';b.className='card';b.dataset.k=c.k;
        b.innerHTML='<div class="lbl"></div><div class="val"></div><div class="word"></div><div class="bar"><i></i></div>';
        b.addEventListener('click',function(){openSheet(c.k)});g.appendChild(b)})}
    p.cards.forEach(function(c){var b=g.querySelector('[data-k="'+c.k+'"]');if(!b)return;
      setText(b.children[0],c.label);setText(b.children[1],c.value);setText(b.children[2],c.word);
      b.children[1].style.color=c.off?'var(--muted)':'';b.children[2].className='word '+(c.off?'':c.cls);if(c.off)b.children[2].style.color='var(--muted)';else b.children[2].style.color='';
      var bar=b.children[3].firstChild;bar.className=c.cls;if(bar.style.width!==c.pct+'%')bar.style.width=c.pct+'%';b.disabled=c.off})}

  // --- reading sheet
  var sheet=$('sheet'),scrim=$('scrim'),sheetK=null;
  function cardOf(p,k){return p.cards.filter(function(c){return c.k===k})[0]}
  function openSheet(k){var p=P();if(!p)return;var c=cardOf(p,k);if(!c||c.off)return;sheetK=k;fillSheet();show(sheet,true);show(scrim,true);
    loadHist('day',p.serial).then(function(){if(sheetK===k)fillSheet()})}
  function fillSheet(){var p=P(),c=p&&cardOf(p,sheetK);if(!c)return;
    setText($('shLabel'),c.label);setText($('shTitle'),c.value);var sw=$('shWord');setText(sw,c.word);sw.className='sh-word '+c.cls;
    var h=HCACHE[p.serial+'|day'],vals=Array.isArray(h&&h.buckets)?h.buckets.map(function(b){return b[sheetK]}).filter(function(v){return v!=null}):[];
    var rows='<div><span>'+esc(p.name)+' wants</span><span>'+esc(c.wants)+'</span></div>';
    if(vals.length)rows+='<div><span>24h low</span><span>'+esc(hFmt(h,sheetK,Math.min.apply(null,vals)))+'</span></div><div><span>24h high</span><span>'+esc(hFmt(h,sheetK,Math.max.apply(null,vals)))+'</span></div>';
    rows+='<div><span>Updated</span><span>'+esc(p.updated)+'</span></div>';$('shRows').innerHTML=rows;
    if(vals.length>=2){drawSpark(vals,h.wants[sheetK]);show($('spark'),true);show(document.querySelector('.sh-axis'),true)}else{$('spark').innerHTML='';show($('spark'),false);show(document.querySelector('.sh-axis'),false)}}
  function closeSheet(){sheetK=null;show(sheet,false);show(scrim,false)}
  scrim.addEventListener('click',closeSheet);$('shClose').addEventListener('click',closeSheet);
  function drawSpark(h,w){
    var W=320,H=90,pad=8,lo=Math.min.apply(null,h),hi=Math.max.apply(null,h);if(hi-lo<2){hi=lo+2}
    var y=function(v){return H-pad-(v-lo)/(hi-lo)*(H-pad*2)};
    var pts=h.map(function(v,i){return [i/(h.length-1)*W,y(v)]});
    var line=pts.map(function(q,i){return (i?'L':'M')+q[0].toFixed(1)+' '+q[1].toFixed(1)}).join('');
    var bt=Math.max(pad,Math.min(H-pad,y(Math.min(w[1],hi)))),bb=Math.max(pad,Math.min(H-pad,y(Math.max(w[0],lo))));
    var last=pts[pts.length-1];
    $('spark').innerHTML='<rect x="0" y="'+bt+'" width="'+W+'" height="'+Math.max(0,bb-bt)+'" fill="var(--green-tint)"/>'+
      '<path d="'+line+'L'+W+' '+H+'L0 '+H+'Z" fill="var(--green-tint)"/>'+
      '<path d="'+line+'" fill="none" stroke="var(--green)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>'+
      '<circle cx="'+last[0]+'" cy="'+last[1]+'" r="4" fill="var(--green)" stroke="var(--surface)" stroke-width="2"/>'}

  // --- hold-and-slide between plants
  var sw=$('swipe'),hintEl=$('swipeHint');
  var hold=null,armed=false,dragging=false,sx=0,sy=0,dx=0,pid=null;
  function reset(){clearTimeout(hold);hold=null;armed=false;dragging=false;sw.classList.remove('armed','drag');sw.style.transform='';sw.style.opacity='';hintEl.classList.remove('show')}
  sw.addEventListener('pointerdown',function(e){if(e.target.closest('button'))return;sx=e.clientX;sy=e.clientY;dx=0;pid=e.pointerId;
    hold=setTimeout(function(){armed=true;sw.classList.add('armed');hintEl.classList.add('show');if(navigator.vibrate)navigator.vibrate(10)},320)});
  sw.addEventListener('pointermove',function(e){if(pid!==e.pointerId)return;var mx=e.clientX-sx,my=e.clientY-sy;
    if(!armed){if(Math.abs(mx)>8||Math.abs(my)>8)reset();return}
    if(!dragging){dragging=true;sw.classList.add('drag');try{sw.setPointerCapture(pid)}catch(x){}}
    dx=mx;var lim=plants().length>1?1:0.25;sw.style.transform='translateX('+(mx*lim)+'px) scale(.985)';sw.style.opacity=String(Math.max(.4,1-Math.abs(mx)/400))});
  function finish(){if(!armed){reset();return}
    var n=plants().length,step=0;if(n>1&&Math.abs(dx)>80)step=dx<0?1:-1;
    if(step){sw.classList.remove('drag');sw.style.transform='translateX('+(step<0?80:-80)+'px)';sw.style.opacity='0';
      setTimeout(function(){cur=(cur+step+n)%n;render();renderHistory();renderPro();sw.classList.add('drag');sw.style.transform='translateX('+(step<0?-60:60)+'px)';sw.style.opacity='0';
        requestAnimationFrame(function(){requestAnimationFrame(function(){sw.classList.remove('drag');sw.style.transform='';sw.style.opacity=''})});setTimeout(reset,340)},220)}
    else{sw.classList.remove('drag');sw.style.transition='transform .22s cubic-bezier(.3,1.4,.4,1),opacity .2s';sw.style.transform='';sw.style.opacity='';setTimeout(function(){sw.style.transition='';reset()},230)}}
  sw.addEventListener('pointerup',finish);sw.addEventListener('pointercancel',reset);sw.addEventListener('lostpointercapture',function(){if(!dragging)reset()});

  // =========================== ALERTS ===========================
  var alertSig='';
  function renderAlerts(){var L=$('alertList'),items=S?S.alerts:[],sig=JSON.stringify(items)+plants().length;if(sig===alertSig)return;alertSig=sig;L.innerHTML='';
    if(!items.length){L.innerHTML='<div class="empty" style="min-height:120px">'+(plants().length?'All quiet. Nothing to do.':'Alerts show up here once a plant is being watched.')+'</div>';return}
    items.forEach(function(it){var e=document.createElement('div');e.className='alert '+it.cls;
      e.innerHTML='<div class="ic"><svg viewBox="0 0 24 24"><path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/></svg></div><div class="tx"><div class="t">'+esc(it.t)+'</div><div class="s">'+esc(it.s)+'</div><div class="when">'+esc(it.when)+'</div></div>';L.appendChild(e)})}

  // =========================== HISTORY ===========================
  var hRange='hour',hMetric='air',hStyle='line',HCACHE={},hPick=-1,hChartGeom=null,hSvg=$('hChart'),hDown=false;
  var LABELS={air:'Air temp',soil:'Soil temp',light:'Sunlight',moist:'Moisture'};
  var MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],WDY=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  function clockD(d){var h=d.getHours(),m=d.getMinutes(),ap=h>=12?'PM':'AM';h=h%12||12;return h+':'+(m<10?'0':'')+m+' '+ap}
  function loadHist(range,serial){var key=serial+'|'+range;if(HCACHE[key]&&HCACHE[key]!=='err')return Promise.resolve(HCACHE[key]);
    return api('/api/app/history?serial='+encodeURIComponent(serial)+'&range='+range).then(function(d){HCACHE[key]=d.ok?d:'err';return HCACHE[key]})}
  function hFmt(h,k,v){if(k==='air'||k==='soil')return Math.round(v)+h.unit_label;return (k==='light'?h.light_words:h.moist_words)[Math.round(v)]}
  function renderHistory(){
    var hc=document.querySelector('#history .hcard'),hEmpty=$('hEmpty'),leg=document.querySelector('#history .hlegend');
    var quiet=function(t){setText($('hTitle'),plants().length?P().name:'History');show(hc,false);show(leg,false);show(hEmpty,!!t);setText(hEmpty,t||'')};
    if(!plants().length)return quiet('Add a plant and its readings build up here.');
    var p=P(),key=p.serial+'|'+hRange,h=HCACHE[key];
    if(h===undefined){quiet('');loadHist(hRange,p.serial).then(function(){if(P()&&P().serial===p.serial)renderHistory()});return}
    if(h==='err')return quiet('Couldn\'t reach Happy Plant. Pull down to try again.');
    var k=hMetric,vals=h.buckets.map(function(b){return b[k]}),real=vals.filter(function(v){return v!=null});
    if(!real.length)return quiet('No '+LABELS[k].toLowerCase()+' readings from '+p.serial+' in this range yet.');
    show(hEmpty,false);show(hc,true);show(leg,true);
    setText($('hTitle'),p.name);setText($('hPlant'),p.name);
    var RN={hour:'last hour',day:'today',week:'this week',month:'this month',year:'this year'};
    setText($('hLbl'),LABELS[k]+' · '+RN[hRange]);
    var lo=Math.min.apply(null,real),hi=Math.max.apply(null,real),avg=real.reduce(function(a,b){return a+b},0)/real.length;
    var pt=h.buckets.map(function(b){var d=new Date(b.t*1000);
      if(hRange==='hour')return clockD(d);if(hRange==='day'){var hh=d.getHours();return (hh%12||12)+(hh>=12?' PM':' AM')}
      if(hRange==='week')return WDY[d.getDay()]+' '+MON[d.getMonth()]+' '+d.getDate();if(hRange==='month')return MON[d.getMonth()]+' '+d.getDate();return MON[d.getMonth()]+' '+d.getFullYear()});
    if(hPick>=0&&hPick<vals.length){setText($('hVal'),vals[hPick]==null?'—':hFmt(h,k,vals[hPick]));setText($('hSub'),pt[hPick]+(vals[hPick]==null?' · no reading':''))}
    else{setText($('hVal'),hFmt(h,k,avg));setText($('hSub'),(k==='air'||k==='soil')?'average · low '+hFmt(h,k,lo)+' · high '+hFmt(h,k,hi):'most of the time · from '+hFmt(h,k,lo)+' to '+hFmt(h,k,hi))}
    var lab;var n=vals.length;
    if(hRange==='week')lab=h.buckets.map(function(b){return WDY[new Date(b.t*1000).getDay()]});
    else if(hRange==='year')lab=h.buckets.map(function(b){return MON[new Date(b.t*1000).getMonth()][0]});
    else{var idx=[0,Math.round((n-1)/4),Math.round((n-1)/2),Math.round(3*(n-1)/4),n-1];
      lab=idx.map(function(i){var d=new Date(h.buckets[i].t*1000);if(i===n-1)return 'now';
        if(hRange==='hour')return Math.round((Date.now()/1000-h.buckets[i].t)/60)+'m';
        if(hRange==='day'){var hh=d.getHours();return (hh%12||12)+(hh>=12?'p':'a')}return String(d.getDate())})}
    var W=340,H=204,padL=(k==='air'||k==='soil')?34:58,padR=10,padT=18,padB=26,w=h.wants[k];
    var yl,yh;if(k==='air'||k==='soil'){yl=Math.floor(Math.min(lo,w[0])/5)*5-5;yh=Math.ceil(Math.max(hi,w[1])/5)*5}else if(k==='light'){yl=0;yh=3.3}else{yl=0;yh=4.3}
    var y=function(v){return padT+(1-(v-yl)/(yh-yl))*(H-padT-padB)},x=function(i){return padL+i/(n-1)*(W-padL-padR)};
    var bt=hStyle==='bar'?y(yh):y(w[1]),bb=hStyle==='bar'?y(yl):y(w[0]);
    var svg='<rect x="'+padL+'" y="'+bt+'" width="'+(W-padL-padR)+'" height="'+(bb-bt)+'" rx="4" fill="var(--green-tint)"/>';
    var ticks=(k==='air'||k==='soil')?[yl,(yl+yh)/2,yh]:(k==='light'?[0,1,2,3]:[0,1,2,3,4]);
    ticks.forEach(function(t){var ty=y(t);svg+='<line x1="'+padL+'" x2="'+(W-padR)+'" y1="'+ty+'" y2="'+ty+'" stroke="var(--line)" stroke-width="1"/>';
      var tl=(k==='air'||k==='soil')?Math.round(t)+'°':(k==='light'?h.light_words[t]:h.moist_words[t]);svg+='<text x="'+(padL-6)+'" y="'+(ty+4)+'" text-anchor="end" font-size="10" fill="var(--muted)">'+tl+'</text>'});
    var bwX=hStyle==='bar'?Math.max(3,(W-padL-padR)/n*0.6):0;
    var lx=function(i){return hStyle==='bar'?padL+6+bwX/2+i/(n-1)*(W-padL-padR-bwX-12):x(i)};
    if(hStyle==='bar'){var base=y(yl);vals.forEach(function(v,i){if(v==null)return;var cx=lx(i),vy=y(v),out=v<w[0]||v>w[1];
        svg+='<rect x="'+(cx-bwX/2)+'" y="'+Math.min(vy,base)+'" width="'+bwX+'" height="'+Math.max(2,Math.abs(base-vy))+'" rx="'+Math.min(3,bwX/2)+'" fill="'+(out?'var(--sand)':'var(--green)')+'"/>'})}
    else{var runs=[],run=[];vals.forEach(function(v,i){if(v==null){if(run.length)runs.push(run);run=[]}else run.push(i)});if(run.length)runs.push(run);
      runs.forEach(function(r){var path=r.map(function(i,j){return (j?'L':'M')+x(i).toFixed(1)+' '+y(vals[i]).toFixed(1)}).join('');
        if(r.length>1)svg+='<path d="'+path+'L'+x(r[r.length-1])+' '+y(yl)+'L'+x(r[0])+' '+y(yl)+'Z" fill="var(--green-tint)"/>';
        svg+=r.length>1?'<path d="'+path+'" fill="none" stroke="var(--green)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>':'<circle cx="'+x(r[0])+'" cy="'+y(vals[r[0]])+'" r="3" fill="var(--green)"/>'});
      var li=-1;for(var q=n-1;q>=0;q--){if(vals[q]!=null){li=q;break}}
      if(li>=0)svg+='<circle cx="'+x(li)+'" cy="'+y(vals[li])+'" r="4.5" fill="var(--green)" stroke="var(--surface)" stroke-width="2"/>'}
    if(lab.length===n){lab.forEach(function(l,i){svg+='<text x="'+lx(i)+'" y="'+(H-8)+'" text-anchor="middle" font-size="10" fill="var(--muted)">'+l+'</text>'})}
    else{lab.forEach(function(l,j){var i=Math.round(j/(lab.length-1)*(n-1));var anchor=j===0?'start':j===lab.length-1?'end':'middle';var px=j===0?Math.max(padL,lx(i)-bwX/2):j===lab.length-1?Math.min(W-padR,lx(i)+bwX/2):lx(i);
      svg+='<text x="'+px+'" y="'+(H-8)+'" text-anchor="'+anchor+'" font-size="10" fill="var(--muted)">'+l+'</text>'})}
    if(hPick>=0&&hPick<n&&vals[hPick]!=null){var px=lx(hPick),py=y(vals[hPick]),txt=hFmt(h,k,vals[hPick]),tw=txt.length*6.5+16,tx=Math.max(padL+tw/2,Math.min(W-padR-tw/2,px));
      svg+='<line x1="'+px+'" x2="'+px+'" y1="'+padT+'" y2="'+(H-padB)+'" stroke="var(--fg)" stroke-width="1" stroke-dasharray="3 3" opacity=".5"/>';
      svg+='<circle cx="'+px+'" cy="'+py+'" r="5.5" fill="var(--fg)" stroke="var(--surface)" stroke-width="2.5"/>';
      svg+='<rect x="'+(tx-tw/2)+'" y="'+(padT-9)+'" width="'+tw+'" height="18" rx="9" fill="var(--fg)"/><text x="'+tx+'" y="'+(padT+4)+'" text-anchor="middle" font-size="11" font-weight="700" fill="var(--bg)">'+txt+'</text>'}
    hSvg.innerHTML=svg;$('hAxis').innerHTML='';hChartGeom={n:n,padL:padL,padR:padR,W:W}}
  function pickFrom(e){if(!hChartGeom)return;var r=hSvg.getBoundingClientRect(),vx=(e.clientX-r.left)/r.width*hChartGeom.W,g=hChartGeom,t=(vx-g.padL)/(g.W-g.padL-g.padR);
    var i=Math.round(Math.max(0,Math.min(1,t))*(g.n-1));if(i!==hPick){hPick=i;renderHistory()}}
  hSvg.addEventListener('pointerdown',function(e){hDown=true;try{hSvg.setPointerCapture(e.pointerId)}catch(x){}pickFrom(e)});
  hSvg.addEventListener('pointermove',function(e){if(hDown)pickFrom(e)});
  function hRelease(){hDown=false;if(hPick!==-1){hPick=-1;renderHistory()}}
  hSvg.addEventListener('pointerup',hRelease);hSvg.addEventListener('pointercancel',hRelease);
  function pressGroup(sel,attr,val){document.querySelectorAll(sel).forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset[attr]===val))})}
  document.querySelectorAll('[data-range]').forEach(function(b){b.addEventListener('click',function(){hRange=b.dataset.range;pressGroup('[data-range]','range',hRange);renderHistory()})});
  document.querySelectorAll('[data-metric]').forEach(function(b){b.addEventListener('click',function(){hMetric=b.dataset.metric;pressGroup('[data-metric]','metric',hMetric);renderHistory()})});
  document.querySelectorAll('[data-style]').forEach(function(b){b.addEventListener('click',function(){hStyle=b.dataset.style;pressGroup('[data-style]','style',hStyle);renderHistory()})});
  setInterval(function(){HCACHE={};if(document.querySelector('#history.active'))renderHistory()},60000);

  // =========================== PLANTS ===========================
  var plantSig='';
  function moodTag(p){return p.mood.cls==='fresh'?'New':p.mood.word}
  function renderPlants(){var L=$('plantList'),ps=plants(),sig=JSON.stringify(ps.map(function(p){return [p.name,p.sub,p.photo,p.mood.cls,p.mood.word]}));if(sig===plantSig)return;plantSig=sig;L.innerHTML='';
    if(!ps.length)L.innerHTML='<div class="empty" style="min-height:140px">No plants yet. Add your first Happy Plant below.</div>';
    ps.forEach(function(p,i){var b=document.createElement('button');b.type='button';b.className='pcard';
      b.innerHTML='<div class="av">'+(p.photo?'<img src="'+esc(p.photo)+'" alt="">':'<svg viewBox="0 0 24 24"><path d="M12 22V12M12 12C8 12 5 9 5 5c4 0 7 3 7 7zM12 12c4 0 7-3 7-7-4 0-7 3-7 7z"/></svg>')+'</div><div class="tx"><div class="t">'+esc(p.name)+'</div><div class="s">'+esc(p.sub)+'</div></div><div class="md '+esc(p.mood.cls)+'">'+esc(moodTag(p))+'</div>';
      b.addEventListener('click',function(){openEditor(i)});L.appendChild(b)})}
  var psheet=$('psheet'),pscrim=$('pscrim'),EDIT=-1,photoData=null,photoChanged=false;
  function fillNeeds(w){$('nAirLo').value=w.air[0];$('nAirHi').value=w.air[1];$('nSoilLo').value=w.soil[0];$('nSoilHi').value=w.soil[1];
    $('nLightLo').value=w.light[0];$('nLightHi').value=w.light[1];$('nMoistLo').value=w.moist[0];$('nMoistHi').value=w.moist[1]}
  function openEditor(i){var p=plants()[i];if(!p)return;EDIT=i;
    setText($('psTitle'),'Edit '+p.name);$('pName').value=p.name;$('pWhere').value=p.where||'';
    photoData=null;photoChanged=false;var img=$('photoImg');if(p.photo){img.src=p.photo;show(img,true);show($('photoHint'),false)}else{show(img,false);show($('photoHint'),true)}
    setText($('nUnit1'),S.settings.unit_label);setText($('nUnit2'),S.settings.unit_label);fillNeeds(p.wants);
    show($('benefits'),false);setText($('lookupS'),'Type a name, then look it up — or set it yourself below');
    var del=$('pDelete');del.dataset.arm='';setText(del,'Remove this plant');show($('pErr'),false);
    show(psheet,true);show(pscrim,true);psheet.scrollTop=0}
  function closeEditor(){show(psheet,false);show(pscrim,false)}
  pscrim.addEventListener('click',closeEditor);$('pCancel').addEventListener('click',closeEditor);
  $('addPlant').addEventListener('click',openPair);
  $('photoIn').addEventListener('change',function(){var f=this.files&&this.files[0];if(!f)return;var rd=new FileReader();rd.onload=function(){
    var im=new Image();im.onload=function(){var c=document.createElement('canvas'),sz=256,sc=Math.max(sz/im.width,sz/im.height);c.width=sz;c.height=sz;var cx=c.getContext('2d');cx.drawImage(im,(sz-im.width*sc)/2,(sz-im.height*sc)/2,im.width*sc,im.height*sc);photoData=c.toDataURL('image/jpeg',.82);photoChanged=true;
      var img=$('photoImg');img.src=photoData;show(img,true);show($('photoHint'),false)};im.src=rd.result};rd.readAsDataURL(f)});
  $('lookupBtn').addEventListener('click',function(){var st=$('lookupS');
    api('/api/app/lookup?name='+encodeURIComponent($('pName').value)).then(function(d){setText(st,d.message||'');
      if(d.ok){fillNeeds(d.wants);show($('benefits'),true);setText($('benefitsTx'),d.about)}else show($('benefits'),false)})});
  $('pform').addEventListener('submit',function(e){e.preventDefault();var p=plants()[EDIT],err=$('pErr');if(!p)return;
    var v=function(id){return Number($(id).value)};
    var data={name:$('pName').value,where:$('pWhere').value,wants:{air:[v('nAirLo'),v('nAirHi')],soil:[v('nSoilLo'),v('nSoilHi')],light:[v('nLightLo'),v('nLightHi')],moist:[v('nMoistLo'),v('nMoistHi')]}};
    if(photoChanged)data.photo=photoData;
    $('pSave').disabled=true;
    api('/api/app/plant/'+encodeURIComponent(p.serial),data).then(function(d){$('pSave').disabled=false;
      if(d.ok){HCACHE={};useState(d);closeEditor()}else{setText(err,d.message);show(err,true)}})});
  $('pDelete').addEventListener('click',function(){var b=this,p=plants()[EDIT];if(!p)return;
    if(b.dataset.arm!=='1'){b.dataset.arm='1';setText(b,'Tap again to remove '+p.name+' and disconnect '+p.serial);return}
    api('/api/units/'+encodeURIComponent(p.serial)+'/remove',{}).then(function(d){if(d.ok){cur=0;closeEditor();refresh()}else{setText($('pErr'),d.message);show($('pErr'),true)}})});

  // =========================== DEVICES ===========================
  var devSig='',DEV=-1,dsheet=$('dsheet'),dscrim=$('dscrim');
  function renderDevices(){var L=$('devList'),ps=plants(),sig=JSON.stringify(ps.map(function(p){return [p.device,p.name]}));if(sig===devSig)return;devSig=sig;L.innerHTML='';
    if(!ps.length)L.innerHTML='<div class="empty" style="min-height:140px">No Happy Plants yet. Add one below with its Happy Key.</div>';
    ps.forEach(function(p,i){var d=p.device,b=document.createElement('button');b.type='button';b.className='pcard dcard';
      b.innerHTML='<div class="av"><svg viewBox="0 0 24 24"><rect x="6" y="3" width="12" height="18" rx="3"/><circle cx="12" cy="9" r="1.6"/><path d="M10 16h4"/></svg></div><div class="tx"><div class="t">'+esc(d.serial)+'</div><div class="s">Watching '+esc(p.name)+'</div><div class="meta"><span class="batt"><b><i style="width:'+d.battery_pct+'%"></i></b>'+esc(d.battery)+'</span><span class="bars" data-n="'+d.wifi_bars+'"><i></i><i></i><i></i><i></i></span><span>'+esc(d.wifi)+'</span></div></div><div class="md '+(d.online?'':'night')+'">'+esc(d.status)+'</div>';
      b.addEventListener('click',function(){openDevice(i)});L.appendChild(b)});
    if(DEV>=0&&!dsheet.hidden)fillDevice()}
  function fillDevice(){var p=plants()[DEV];if(!p)return closeDevice();var d=p.device;
    setText($('dsTitle'),d.serial);var st=$('dsStatus');setText(st,d.status);st.className='sh-word '+(d.online?'':'off');
    setText($('dsBatt'),d.battery);$('dsBattBar').style.width=d.battery_pct+'%';setText($('dsWifi'),d.wifi);$('dsBars').setAttribute('data-n',d.wifi_bars);
    $('dsRows').innerHTML=d.rows.map(function(r){return '<div><span>'+esc(r[0])+'</span><span>'+esc(r[1])+'</span></div>'}).join('')}
  function openDevice(i){DEV=i;fillDevice();var f=$('dForget');f.dataset.arm='';setText(f,'Forget this device');show(dsheet,true);show(dscrim,true);dsheet.scrollTop=0}
  function closeDevice(){DEV=-1;show(dsheet,false);show(dscrim,false)}
  dscrim.addEventListener('click',closeDevice);$('dCancel').addEventListener('click',closeDevice);
  $('dForget').addEventListener('click',function(){var b=this,p=plants()[DEV];if(!p)return;
    if(b.dataset.arm!=='1'){b.dataset.arm='1';setText(b,'Tap again to forget '+p.serial);return}
    api('/api/units/'+encodeURIComponent(p.serial)+'/remove',{}).then(function(d){if(d.ok){cur=0;closeDevice();refresh()}})});

  // =========================== ADD A HAPPY PLANT (pair with the Happy Key) ===========================
  var wsheet=$('wsheet'),wscrim=$('wscrim'),pairSerial=null;
  function wz(n){[1,2,3].forEach(function(i){show($('wz'+i),i===n)});document.querySelectorAll('#wzSteps i').forEach(function(e,i){e.classList.toggle('on',i<n)})}
  function openPair(){pairSerial=null;wz(1);$('wzKey').value='';show($('wzErr'),false);show($('wzLocErr'),false);show($('wzNameErr'),false);show(wsheet,true);show(wscrim,true);wsheet.scrollTop=0;setTimeout(function(){$('wzKey').focus()},60)}
  function closePair(){show(wsheet,false);show(wscrim,false)}
  $('wizOpen').addEventListener('click',openPair);$('wizOpen2').addEventListener('click',openPair);wscrim.addEventListener('click',closePair);
  document.querySelectorAll('[data-add]').forEach(function(b){b.addEventListener('click',openPair)});
  $('wzPair').addEventListener('click',function(){var er=$('wzErr'),btn=this;btn.disabled=true;
    api('/api/units/pair',{key:$('wzKey').value}).then(function(d){btn.disabled=false;
      if(!d.ok){setText(er,d.message);show(er,true);return}
      show(er,false);pairSerial=d.unit.serial;refresh();
      if(S&&S.settings.has_location){wz(3);$('wzName').value='';$('wzWhere').value=''}else wz(2)})});
  $('wzLoc').addEventListener('click',function(){var er=$('wzLocErr');
    locate().then(function(c){return api('/api/app/settings',c)}).then(function(d){if(d.ok){useState(d);wz(3);$('wzName').value='';$('wzWhere').value=''}else{setText(er,d.message);show(er,true)}})
      .catch(function(){setText(er,'Location is off. You can set it later in Settings.');show(er,true)})});
  $('wzSkip').addEventListener('click',function(){wz(3);$('wzName').value='';$('wzWhere').value=''});
  $('wzFinish').addEventListener('click',function(){var er=$('wzNameErr');if(!pairSerial)return;
    api('/api/app/plant/'+encodeURIComponent(pairSerial),{name:$('wzName').value,where:$('wzWhere').value}).then(function(d){
      if(!d.ok){setText(er,d.message);show(er,true);return}
      useState(d);var ps=plants();for(var i=0;i<ps.length;i++){if(ps[i].serial===pairSerial)cur=i}render();closePair();go('home')})});

  // =========================== PRO ===========================
  function renderPro(){var p=P();setText($('tipPlant'),p?p.name:'your plant');
    var html=p?p.tips.map(function(t){return '<div class="tip"><b>'+esc(t.b)+'</b>'+esc(t.s)+'</div>'}).join(''):'<div class="empty" style="min-height:80px">Add a plant to see tips.</div>';
    var L=$('tipList');if(L.innerHTML!==html)L.innerHTML=html}

  // =========================== EVERYTHING ===========================
  function renderAll(){render();renderAlerts();renderPlants();renderDevices();renderSettings();renderPro();if(sheetK)fillSheet();if(document.querySelector('#history.active'))renderHistory()}

  // Quiet background refresh: numbers change in place, nothing on screen disappears or reloads.
  setInterval(function(){if(S&&!document.hidden)refresh()},10000);
  document.addEventListener('visibilitychange',function(){if(!document.hidden)refresh()});

  // =========================== SIGN IN ===========================
  var auth=$('auth'),form=$('authForm'),err=$('authErr'),mode='in',authEmail='';
  function say(t){setText(err,t||'');show(err,!!t)}
  var MODES={
    in:{h:'Sign in',btn:'Sign in',swap:'New here? Create an account',extra:'Forgot password',f:['email','pass']},
    up:{h:'Create account',btn:'Create account',swap:'Have an account? Sign in',extra:'',f:['fname','email','pass','pass2']},
    verify:{h:'Check your email',btn:'Confirm',swap:'Back to sign in',extra:'Send a new code',f:['code']},
    forgot:{h:'Reset password',btn:'Send code',swap:'Back to sign in',extra:'',f:['email']},
    reset:{h:'New password',btn:'Set new password',swap:'Back to sign in',extra:'Send a new code',f:['code','pass','pass2']}};
  var WRAP={fname:'fnameWrap',email:'emailWrap',pass:'passWrap',pass2:'pass2Wrap',code:'codeWrap'};
  function setMode(m,note){mode=m;var c=MODES[m];say('');
    setText($('authH'),c.h);setText($('authBtn'),c.btn);setText($('authSwap'),c.swap);setText($('authForgot'),c.extra);show($('authForgot'),!!c.extra);
    Object.keys(WRAP).forEach(function(k){show($(WRAP[k]),c.f.indexOf(k)>=0)});
    setText($('authNote'),note||'');show($('authNote'),!!note);
    setText($('passLbl'),m==='reset'?'New password':'Password');$('pass').autocomplete=m==='in'?'current-password':'new-password';
    if(m==='verify'||m==='reset'){$('code').value='';setTimeout(function(){$('code').focus()},50)}}
  function showAuth(on){show(auth,on);if(on){setMode('in');$('pass').value='';setTimeout(function(){$('email').focus()},50)}}
  function enter(d){S=d;cur=0;cardKeys='';alertSig=plantSig=devSig='';HCACHE={};showAuth(false);go('home');renderAll()}
  function afterLogin(){return api('/api/app/state').then(function(d){if(d.ok)enter(d);else say(d.message)})}
  form.addEventListener('submit',function(e){e.preventDefault();var btn=$('authBtn');btn.disabled=true;var done=function(){btn.disabled=false};
    var em=$('email').value.trim(),pw=$('pass').value,pw2=$('pass2').value,code=$('code').value;
    if(mode==='in')api('/api/auth/login',{email:em,password:pw}).then(function(d){done();authEmail=d.email||em;
      if(d.ok)return afterLogin();if(d.error==='verify_email')return setMode('verify',d.message);say(d.message)});
    else if(mode==='up')api('/api/auth/signup',{first_name:$('fname').value,email:em,password:pw,password2:pw2}).then(function(d){done();
      if(d.ok){authEmail=d.email;setMode('verify',d.message)}else say(d.message)});
    else if(mode==='verify')api('/api/auth/verify',{email:authEmail,code:code}).then(function(d){done();if(d.ok)return afterLogin();say(d.message)});
    else if(mode==='forgot')api('/api/auth/reset/request',{email:em}).then(function(d){done();if(d.ok){authEmail=d.email;setMode('reset',d.message)}else say(d.message)});
    else if(mode==='reset')api('/api/auth/reset/confirm',{email:authEmail,code:code,new_password:pw,password2:pw2}).then(function(d){done();if(d.ok)return afterLogin();say(d.message)})});
  $('authSwap').addEventListener('click',function(){setMode(mode==='in'?'up':'in')});
  $('authForgot').addEventListener('click',function(){
    if(mode==='in')return setMode('forgot');
    api('/api/auth/resend',{email:authEmail,purpose:mode==='reset'?'reset':'verify'}).then(function(d){say(d.message)})});
  $('signOut').addEventListener('click',function(){api('/api/auth/logout',{}).then(function(){S=null;showAuth(true)})});

  if(S&&S.plants){enter(S)}else{showAuth(true)}
})();
