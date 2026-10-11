(() => {
  'use strict';
  const D = window.LIMA_DATA, $ = s => document.querySelector(s);
  if (!D) { document.body.innerHTML = '<p style="padding:30px">Falta data/data.js. Ejecuta: python py/make_data.py</p>'; return; }
  const Y = D.years, N = Y.length, hasL = !!window.L;
  const st = {i:N-1, a:0, v:'pct', sel:null, op:.65, lbl:false, ras:false, timer:null};
  const RAMP = ['#ffe9a8','#fdae61','#e8503a','#7f0f2a'];
  const TYPE = {'Consolidado':'#0e9aa7','En consolidación':'#f08a2b','Expansión acelerada':'#e0392f','Emergente':'#e5c038'};
  const f1 = x => x == null ? 's/d' : (Math.round(x*10)/10).toLocaleString('es-PE');

  const met = d => {
    const b = d.built[st.i], a = d.built[st.a], yrs = Y[st.i]-Y[st.a], pct = 100*b/d.area, gs = 100*(b-a)/d.area;
    const cagr = a > 0 && yrs > 0 ? (Math.pow(b/a,1/yrs)-1)*100 : null;
    const dec = yrs > 0 ? gs/(yrs/10) : 0, type = pct >= 60 && dec < 4 ? 'Consolidado' : dec >= 4 ? 'Expansión acelerada' : pct >= 15 ? 'En consolidación' : 'Emergente';
    return {b, a, pct, delta:b-a, cagr, gs, type};
  };
  const VARS = {
    pct:{l:'% urbanizado',g:x=>x.pct,t:[10,30,60],u:' %'},
    km2:{l:'Área construida (km²)',g:x=>x.b,t:[3,10,25],u:' km²'},
    delta:{l:'Expansión: km² nuevos (base→año)',g:x=>x.delta,t:[1,4,10],u:' km²'},
    cagr:{l:'Crecimiento anual (TCAC %)',g:x=>x.cagr,t:[1,3,6],u:' %'},
    type:{l:'Tipología de expansión',g:x=>x.delta,cat:true,u:' km²'}
  };
  $('#vari').innerHTML = Object.entries(VARS).map(([k,v]) => `<option value="${k}">${v.l}</option>`).join('');
  const color = (x,m) => { if (VARS[st.v].cat) return TYPE[m.type]; if (x == null) return '#888'; const t = VARS[st.v].t; return RAMP[x<t[0]?0:x<t[1]?1:x<t[2]?2:3]; };

  // ---- Mapa
  let map, bases, base, grp, rasLayer;
  if (hasL) {
    const PERU = [[-18.5,-81.5],[0.2,-68.5]];
    map = L.map('map',{minZoom:5,maxBounds:[[-20,-83],[1.5,-67]],zoomSnap:.25}).setView([-12.05,-76.95],10);
    map.createPane('ras').style.zIndex = 350;
    const A = '© OpenStreetMap · CARTO · Esri';
    bases = {sat:L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{attribution:A}),
      dark:L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:A}),
      light:L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',{attribution:A}),
      topo:L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',{attribution:A})};
    base = bases.sat.addTo(map); grp = L.layerGroup().addTo(map);
    $('#bPeru').onclick = () => map.flyToBounds(PERU); $('#bLima').onclick = () => map.flyToBounds(D.bbox || [[-12.58,-77.25],[-11.55,-76.55]]);
  } else { $('#bPeru').hidden = $('#bLima').hidden = true; }

  const fx = lo => (lo+77.22)*1000, fy = la => (-la-11.58)*1000;
  function drawFallback(rows){
    const g = rows.map(r => `<g data-n="${r.d.name}" style="cursor:pointer"><path d="${r.d.rings.map(q => 'M'+q.map(([la,lo]) => fx(lo).toFixed(0)+','+fy(la).toFixed(0)).join('L')+'Z').join('')}" fill="${r.col}" fill-opacity="${st.op}" stroke="${st.sel===r.d.name?'#c9a24b':'#fff'}" stroke-width="${st.sel===r.d.name?4:1}"><title>${r.d.name}: ${f1(r.x)}${VARS[st.v].u}</title></path>${st.lbl?`<text x="${fx(r.d.lon)}" y="${fy(r.d.lat)}" text-anchor="middle" fill="#fff" font-size="13" font-weight="700" pointer-events="none">${r.d.name}</text>`:''}</g>`).join('');
    $('#map').innerHTML = `<div class="fb"><svg viewBox="-30 -30 700 1030" role="img" aria-label="Mapa esquemático de Lima">${g}</svg><div class="fbn">Mapa sin conexión · límites ${D.geom}</div></div>`;
    $('#map').onclick = e => { const n = e.target.closest('g[data-n]'); if (n) select(n.dataset.n); };
  }

  function draw(rows){
    if (!hasL) return drawFallback(rows);
    grp.clearLayers();
    rows.forEach(r => {
      const on = st.sel === r.d.name;
      const p = L.polygon(r.d.rings.map(q => [q]),{color:on?'#c9a24b':'#fff',weight:on?3:.8,fillColor:r.col,fillOpacity:st.op}).on('click',() => select(r.d.name,true));
      st.lbl ? p.bindTooltip(r.d.name,{permanent:true,direction:'center',className:'lbl'}) : p.bindTooltip(`<b>${r.d.name}</b><br>${f1(r.x)}${VARS[st.v].u}`,{sticky:true});
      p.addTo(grp);
    });
    if (rasLayer) { map.removeLayer(rasLayer); rasLayer = null; }
    if (st.ras && D.rasters) rasLayer = L.imageOverlay(D.rasters[Y[st.i]],D.bbox,{pane:'ras',opacity:.95}).addTo(map);
  }

  // ---- Gráficos
  function line(cv, vals, hi, base){
    const r = devicePixelRatio||1, w = cv.clientWidth, h = cv.height; cv.width = w*r; cv.height = h*r; cv.style.height = h+'px';
    const g = cv.getContext('2d'); g.scale(r,r); const max = Math.max(...vals)*1.1||1, px = i => 30+i*(w-40)/(N-1), py = v => h-18-v/max*(h-30);
    g.font = '10px system-ui'; g.fillStyle = '#8fb0c2'; g.strokeStyle = '#ffffff1f';
    [0,.5,1].forEach(k => {const v = max/1.1*k; g.beginPath();g.moveTo(28,py(v));g.lineTo(w-6,py(v));g.stroke();g.fillText(Math.round(v),2,py(v)+3);});
    g.beginPath(); vals.forEach((v,i) => i ? g.lineTo(px(i),py(v)) : g.moveTo(px(i),py(v))); g.lineTo(px(N-1),py(0)); g.lineTo(px(0),py(0)); g.closePath(); g.fillStyle = '#e8503a33'; g.fill();
    g.beginPath(); vals.forEach((v,i) => i ? g.lineTo(px(i),py(v)) : g.moveTo(px(i),py(v))); g.strokeStyle = '#fdae61'; g.lineWidth = 2; g.stroke();
    [[base,'#4fd1e8'],[hi,'#fff']].forEach(([i,c]) => {g.beginPath();g.arc(px(i),py(vals[i]),4,0,7);g.fillStyle = c;g.fill();});
    g.fillStyle = '#8fb0c2'; g.fillText(Y[0],26,h-4); g.fillText(Y[N-1],w-30,h-4);
  }

  // ---- Render
  function render(){
    const V = VARS[st.v];
    const rows = D.deps.map(d => {const m = met(d), x = V.g(m); return {d,m,x,col:color(x,m)};});
    draw(rows);
    const tot = i => D.deps.reduce((s,d) => s+d.built[i],0), T = Y.map((_,i) => tot(i));
    const yrs = Y[st.i]-Y[st.a], top = [...rows].sort((a,b) => b.m.delta-a.m.delta)[0];
    $('#yTxt').textContent = Y[st.i]; $('#yb').textContent = Y[st.i]; $('#kTot').textContent = f1(T[st.i]);
    $('#kGr').textContent = T[st.a] > 0 && yrs > 0 ? '+' + Math.round(100*(T[st.i]/T[st.a]-1)) + ' %' : '–';
    $('#kRate').textContent = yrs > 0 ? f1((T[st.i]-T[st.a])/yrs) : '–'; $('#kTop').textContent = yrs > 0 ? `${top.d.name} (+${f1(top.m.delta)} km²)` : '–';
    line($('#cityChart'),T,st.i,st.a);
    $('#rank').innerHTML = [...rows].sort((a,b) => (b.x??-1)-(a.x??-1)).map((r,i) =>
      `<li tabindex="0" data-n="${r.d.name}" class="${st.sel===r.d.name?'on':''}"><span>${i+1}</span><i class="dot" style="background:${r.col}"></i><span class="n">${r.d.name}</span><span class="v">${f1(r.x)}${V.u}</span></li>`).join('');
    const t = V.t;
    $('#legend').innerHTML = `<b>${V.l}</b>` + (V.cat ? Object.entries(TYPE).map(([k,c]) => `<div><i style="background:${c}"></i>${k}</div>`).join('')
      : [`< ${t[0]}`,`${t[0]}–${t[1]}`,`${t[1]}–${t[2]}`,`≥ ${t[2]}`].map((s,i) => `<div><i style="background:${RAMP[i]}"></i>${s}</div>`).join('')) + `<small>Límites ${D.geom}</small>`;
    if (st.sel) detail();
  }

  function detail(){
    const d = D.deps.find(x => x.name === st.sel), m = met(d);
    $('#detail').innerHTML = `<h2>Distrito</h2><h3>${d.name}</h3><span class="badge" style="background:${TYPE[m.type]}">${m.type}</span>
      <div class="kv"><span>Área distrital</span><span>${f1(d.area)} km²</span><span>Construido ${Y[st.i]}</span><span>${f1(m.b)} km²</span><span>% urbanizado</span><span>${f1(m.pct)} %</span>
      <span>Construido ${Y[st.a]}</span><span>${f1(m.a)} km²</span><span>Expansión</span><span>+${f1(m.delta)} km²</span><span>TCAC</span><span>${m.cagr==null?'s/d':f1(m.cagr)+' %'}</span></div>
      <canvas id="dsp" height="90"></canvas><p class="leg">Evolución del área construida (km²)</p>`;
    line($('#dsp'),d.built,st.i,st.a);
  }
  function select(n,fly){
    st.sel = n; render();
    if (fly && hasL) { const d = D.deps.find(x => x.name === n); map.flyToBounds(L.latLngBounds(d.rings.flat()),{maxZoom:13,padding:[30,30]}); }
  }

  // ---- Controles
  const yr = $('#yr'); yr.max = N-1; yr.value = st.i;
  $('#ticks').innerHTML = Y.filter((_,i) => i%2===0 || i===N-1).map(y => `<span>${y}</span>`).join('');
  $('#base').innerHTML = Y.slice(0,-1).map((y,i) => `<option value="${i}">${y}</option>`).join('');
  yr.oninput = () => {st.i = +yr.value; render();};
  $('#base').onchange = e => {st.a = +e.target.value; render();};
  $('#vari').onchange = e => {st.v = e.target.value; render();};
  $('#op').oninput = e => {st.op = e.target.value/100; render();};
  $('#lbl').onchange = e => {st.lbl = e.target.checked; render();};
  const hasR = !!(D.rasters && D.bbox); $('#ras').disabled = !hasL || !hasR;
  $('#rasNote').textContent = hasR ? 'Capa raster real de GHSL por época.' : 'Disponible al ejecutar gee_expansion.py (datos reales).';
  $('#ras').onchange = e => {st.ras = e.target.checked; render();};
  $('#bm').onchange = e => {if (!hasL) return; map.removeLayer(base); base = bases[e.target.value].addTo(map); base.bringToBack();};
  $('#play').onclick = () => {
    if (st.timer) { clearInterval(st.timer); st.timer = null; $('#play').textContent = '▶ Reproducir'; return; }
    $('#play').textContent = '⏸ Pausar';
    st.timer = setInterval(() => {st.i = st.i >= N-1 ? Math.min(st.a+1,N-1) : st.i+1; yr.value = st.i; render();}, 900);
  };
  $('#rank').onclick = e => {const li = e.target.closest('li'); if (li) select(li.dataset.n,true);};
  $('#rank').onkeydown = e => {if (e.key === 'Enter') {const li = e.target.closest('li'); if (li) select(li.dataset.n,true);}};
  $('#bMet').onclick = () => $('#dMet').showModal();
  $('#bCsv').onclick = () => {
    const rows = D.deps.map(d => [d.name,d.area,...d.built].join(','));
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['\ufeff'+['Distrito,Area_km2,'+Y.map(y => 'Construido_km2_'+y).join(',')].concat(rows).join('\n')],{type:'text/csv'}));
    a.download = 'expansion_urbana_lima.csv'; a.click();
  };
  $('#demo').hidden = !D.demo; $('#src').textContent = 'Fuente: ' + D.source; $('#upd').textContent = 'Actualizado ' + D.updated; $('#y').textContent = new Date().getFullYear();
  addEventListener('resize', render); render();
})();
