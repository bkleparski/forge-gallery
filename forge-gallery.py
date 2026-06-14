#!/usr/bin/env python3
"""Forge Gallery — przeglądarka, zarządzanie i organizacja outputs Forge"""

import html, json, mimetypes, os, secrets, hashlib, shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, quote, parse_qs

OUTPUTS_DIR = Path(os.environ.get('FG_OUTPUTS_DIR', '/home/bartek/forge/outputs'))
PORT        = int(os.environ.get('FG_PORT', '7861'))
IMAGE_EXTS  = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}

_username  = os.environ.get('FG_USERNAME', 'admin')
_pw_hash   = os.environ.get('FG_PASSWORD_HASH', '')
if not _pw_hash:
    raise SystemExit(
        'ERROR: FG_PASSWORD_HASH not set.\n'
        'Generate with: python3 -c "import hashlib; print(hashlib.sha256(b\'your-pass\').hexdigest())"'
    )
USERS = {_username: _pw_hash}
SESSIONS = set()
COOKIE_NAME = 'fg_sess'

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Forge Gallery — logowanie</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}
.box{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:40px 36px;width:100%;max-width:360px;box-shadow:0 24px 60px rgba(0,0,0,.5)}
.logo{font-size:1.5rem;font-weight:700;color:#60a5fa;text-align:center;margin-bottom:8px}
.sub{text-align:center;color:#64748b;font-size:.85rem;margin-bottom:28px}
label{display:block;font-size:.8rem;color:#94a3b8;margin-bottom:5px}
input{width:100%;background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:10px 14px;border-radius:8px;font-size:.95rem;outline:none;transition:border .2s;margin-bottom:16px}
input:focus{border-color:#3b82f6}
button{width:100%;background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;border:none;padding:11px;border-radius:8px;font-size:.95rem;font-weight:600;cursor:pointer;transition:opacity .2s;margin-top:4px}
button:hover{opacity:.88}
.err{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.35);color:#fca5a5;padding:10px 14px;border-radius:8px;font-size:.83rem;margin-bottom:16px;text-align:center}
</style>
</head>
<body>
<div class="box">
  <div class="logo">🖼 Forge Gallery</div>
  <div class="sub">Zaloguj się, aby przeglądać</div>
  {ERROR}
  <form method="POST" action="/login">
    <label>Login</label>
    <input type="text" name="username" autofocus autocomplete="username">
    <label>Hasło</label>
    <input type="password" name="password" autocomplete="current-password">
    <button type="submit">Zaloguj</button>
  </form>
</div>
</body>
</html>"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Forge Gallery</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;min-height:100vh}
header{background:#1e293b;border-bottom:1px solid #334155;padding:10px 20px;display:flex;align-items:center;gap:8px;position:sticky;top:0;z-index:10;flex-wrap:wrap}
.logo{font-weight:700;color:#60a5fa;font-size:1.1rem;white-space:nowrap}
.breadcrumb{flex:1;font-size:.85rem;color:#94a3b8;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.breadcrumb a{color:#60a5fa;text-decoration:none}
.breadcrumb a:hover{text-decoration:underline}
.btn{background:#334155;color:#e2e8f0;border:none;padding:6px 13px;border-radius:6px;cursor:pointer;font-size:.82rem;text-decoration:none;display:inline-flex;align-items:center;gap:4px;transition:background .2s;white-space:nowrap}
.btn:hover{background:#475569}
.btn.primary{background:#1d4ed8}.btn.primary:hover{background:#2563eb}
.btn.danger{background:#7f1d1d;color:#fca5a5}.btn.danger:hover{background:#991b1b}
.view-toggle{display:flex;gap:2px;background:#0f172a;border-radius:7px;padding:2px}
.view-btn{background:none;border:none;color:#64748b;padding:5px 9px;border-radius:5px;cursor:pointer;font-size:1rem;transition:all .2s;line-height:1}
.view-btn.active{background:#334155;color:#e2e8f0}
main{padding:20px;max-width:1600px;margin:0 auto}
.section-title{font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;color:#64748b;margin:16px 0 10px;display:flex;align-items:center;gap:8px}
.section-title span{flex:1}

/* === DIRS === */
.dir-card{background:#1e293b;border:1px solid #334155;border-radius:10px;text-decoration:none;color:#e2e8f0;display:flex;transition:all .2s;position:relative;cursor:pointer}
.dir-card:hover{border-color:#60a5fa;background:#243552;transform:translateY(-1px)}
.dir-move-btn{position:absolute;top:6px;right:6px;background:#1e3a5f;border:1px solid #3b82f6;color:#93c5fd;border-radius:6px;padding:3px 8px;font-size:.72rem;cursor:pointer;opacity:0;transition:opacity .15s;z-index:2;line-height:1.4}
.dir-card:hover .dir-move-btn{opacity:1}
.dir-icon{font-size:1.4rem;flex-shrink:0}
.dir-name{font-weight:600;font-size:.92rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dir-count{font-size:.72rem;color:#64748b}
.dir-info{overflow:hidden}

/* grid */
#dirs-container.dirs-grid{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:24px}
#dirs-container.dirs-grid .dir-card{flex-direction:column;padding:14px;min-width:200px;max-width:340px}
#dirs-container.dirs-grid .dir-main{display:flex;align-items:center;gap:10px}
#dirs-container.dirs-grid .dir-previews{display:flex;gap:3px;margin-top:10px;width:100%;height:48px;overflow:hidden}
#dirs-container.dirs-grid .dir-previews img{width:44px;height:44px;object-fit:cover;border-radius:4px;flex-shrink:0;border:1px solid #334155}

/* list */
#dirs-container.dirs-list{display:flex;flex-direction:column;gap:4px;margin-bottom:24px}
#dirs-container.dirs-list .dir-card{flex-direction:row;align-items:center;gap:12px;padding:10px 14px;width:100%}
#dirs-container.dirs-list .dir-main{display:flex;align-items:center;gap:10px;flex:1;min-width:0}
#dirs-container.dirs-list .dir-info{flex:1;min-width:0}
#dirs-container.dirs-list .dir-previews{display:flex;gap:3px;height:42px;flex-shrink:0}
#dirs-container.dirs-list .dir-previews img{width:38px;height:38px;object-fit:cover;border-radius:4px;border:1px solid #334155}

/* === IMAGES === */
.img-card{position:relative;border-radius:8px;overflow:hidden;background:#1e293b;border:1px solid #334155;cursor:pointer;transition:all .2s}
.img-card:hover{border-color:#60a5fa;transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.4)}
.img-card.selected{border-color:#3b82f6 !important;box-shadow:0 0 0 2px rgba(59,130,246,.45)}

/* grid */
#imgs-container.imgs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
#imgs-container.imgs-grid .img-card{aspect-ratio:1}
#imgs-container.imgs-grid .img-card img{width:100%;height:100%;object-fit:cover;display:block}
#imgs-container.imgs-grid .img-overlay{position:absolute;bottom:0;left:0;right:0;background:linear-gradient(transparent,rgba(0,0,0,.88));padding:28px 10px 10px;opacity:0;transition:opacity .2s}
#imgs-container.imgs-grid .img-card:hover .img-overlay{opacity:1}
#imgs-container.imgs-grid .img-card.selected .img-overlay{opacity:1}
#imgs-container.imgs-grid .cb-wrap{position:absolute;top:8px;left:8px;z-index:3;opacity:0;transition:opacity .15s}
#imgs-container.imgs-grid .img-card:hover .cb-wrap,
#imgs-container.imgs-grid .img-card.selected .cb-wrap{opacity:1}

/* list */
#imgs-container.imgs-list{display:flex;flex-direction:column;gap:3px}
#imgs-container.imgs-list .img-card{aspect-ratio:unset;display:flex;flex-direction:row;align-items:center;height:62px;padding:6px 10px;gap:10px;border-radius:7px}
#imgs-container.imgs-list .cb-wrap{position:static;opacity:1;order:0;display:flex;align-items:center}
#imgs-container.imgs-list .img-card img{width:50px;height:50px;object-fit:cover;border-radius:5px;flex-shrink:0;order:1}
#imgs-container.imgs-list .img-overlay{position:static;background:none;padding:0;opacity:1;display:flex;flex:1;align-items:center;gap:8px;min-width:0;order:2}
#imgs-container.imgs-list .img-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.82rem}
#imgs-container.imgs-list .img-meta{flex-shrink:0;margin-bottom:0;font-size:.72rem;white-space:nowrap}
#imgs-container.imgs-list .img-actions{opacity:1;flex-shrink:0}

/* shared overlay parts */
.img-name{font-size:.72rem;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.img-meta{font-size:.65rem;color:#94a3b8;margin-bottom:6px}
.img-actions{display:flex;gap:5px}
.img-actions button{background:rgba(255,255,255,.13);border:none;color:#fff;height:26px;padding:0 8px;border-radius:5px;cursor:pointer;font-size:.8rem;transition:background .2s;display:flex;align-items:center;gap:3px}
.img-actions button:hover{background:rgba(255,255,255,.28)}
.img-actions button.del{background:rgba(239,68,68,.25)}
.img-actions button.del:hover{background:rgba(239,68,68,.55)}
.img-cb{width:18px;height:18px;cursor:pointer;accent-color:#3b82f6;display:block}
.empty{color:#475569;text-align:center;padding:60px;font-size:1.1rem}

/* Lightbox */
#lightbox{display:none;position:fixed;inset:0;background:rgba(0,0,0,.93);z-index:1000;align-items:center;justify-content:center}
#lightbox.open{display:flex}
#lb-img{max-width:90vw;max-height:86vh;object-fit:contain;border-radius:4px;box-shadow:0 0 60px rgba(0,0,0,.8)}
#lb-toolbar{position:fixed;top:0;left:0;right:0;display:flex;align-items:center;padding:10px 16px;background:rgba(15,23,42,.9);backdrop-filter:blur(8px);z-index:1001;gap:8px;flex-wrap:wrap}
#lb-filename{flex:1;font-size:.85rem;color:#94a3b8;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#lb-counter{font-size:.8rem;color:#64748b;white-space:nowrap}
.lb-btn{background:#334155;border:none;color:#e2e8f0;padding:7px 13px;border-radius:6px;cursor:pointer;font-size:.82rem;transition:background .2s;text-decoration:none;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
.lb-btn:hover{background:#475569}
.lb-btn.del{background:#7f1d1d;color:#fca5a5}.lb-btn.del:hover{background:#991b1b}
#lb-nav-left,#lb-nav-right{position:fixed;top:50%;transform:translateY(-50%);background:rgba(51,65,85,.8);border:none;color:#fff;width:48px;height:64px;border-radius:8px;font-size:1.8rem;cursor:pointer;z-index:1001;transition:background .2s;display:flex;align-items:center;justify-content:center}
#lb-nav-left{left:10px}#lb-nav-right{right:10px}
#lb-nav-left:hover,#lb-nav-right:hover{background:rgba(71,85,105,.95)}

/* Bulk bar */
#bulk-bar{position:fixed;bottom:28px;left:50%;transform:translateX(-50%) translateY(100px);background:#1e293b;border:1px solid #3b82f6;border-radius:12px;padding:10px 16px;display:flex;align-items:center;gap:8px;z-index:500;transition:transform .25s;box-shadow:0 8px 32px rgba(0,0,0,.5);white-space:nowrap;flex-wrap:wrap;justify-content:center}
#bulk-bar.show{transform:translateX(-50%) translateY(0)}
#bulk-count{font-size:.85rem;color:#93c5fd;font-weight:600;min-width:80px}
.bar-btn{background:#334155;border:none;color:#e2e8f0;padding:6px 13px;border-radius:6px;cursor:pointer;font-size:.82rem;transition:background .2s}
.bar-btn:hover{background:#475569}
.bar-btn.del{background:#7f1d1d;color:#fca5a5}.bar-btn.del:hover{background:#991b1b}
.bar-btn.move{background:#1e3a8a;color:#bfdbfe}.bar-btn.move:hover{background:#1d4ed8}

/* Toast */
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:10px 20px;border-radius:8px;font-size:.85rem;z-index:2000;transition:transform .3s;pointer-events:none}
#toast.show{transform:translateX(-50%) translateY(0)}
#toast.ok{border-color:#22c55e;color:#86efac}
#toast.err{border-color:#ef4444;color:#fca5a5}

/* Modals */
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:1500;align-items:center;justify-content:center}
.modal.open{display:flex}
.modal-box{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:24px 28px;width:100%;max-width:440px;box-shadow:0 24px 60px rgba(0,0,0,.6)}
.modal-box h3{font-size:1rem;font-weight:600;color:#e2e8f0;margin-bottom:16px}
.modal-input{width:100%;background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:9px 13px;border-radius:7px;font-size:.9rem;outline:none;transition:border .2s;margin-bottom:4px}
.modal-input:focus{border-color:#3b82f6}
.modal-btns{display:flex;gap:8px;justify-content:flex-end;margin-top:14px}
.folder-list{max-height:280px;overflow-y:auto;display:flex;flex-direction:column;gap:3px;margin:8px 0}
.folder-opt{padding:8px 12px;border-radius:6px;cursor:pointer;font-size:.86rem;color:#94a3b8;transition:all .2s;border:1px solid transparent;display:flex;align-items:center;gap:8px}
.folder-opt:hover{background:#334155;color:#e2e8f0}
.folder-opt.sel{background:#1e3a5f;border-color:#3b82f6;color:#93c5fd}
.no-dirs{color:#475569;text-align:center;padding:20px;font-size:.85rem}

/* ── Mobile responsive ── */
@media(max-width:640px){
  header{flex-wrap:wrap;padding:8px 12px;gap:6px}
  .logo{font-size:.95rem}
  .breadcrumb{order:10;width:100%;font-size:.78rem;border-top:1px solid #1e3a5f;padding-top:6px;margin-top:2px}
  .btn{padding:5px 9px;font-size:.76rem}
  main{padding:12px}
  #imgs-container.imgs-grid{grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:6px}
  #dirs-container.dirs-grid{gap:6px}
  #dirs-container.dirs-grid .dir-card{min-width:calc(50% - 3px);max-width:100%;flex:1 1 calc(50% - 3px)}
  .section-title{font-size:.7rem;margin:12px 0 7px}
  #lb-toolbar{flex-wrap:wrap;gap:5px;padding:8px 10px}
  #lb-filename{width:100%;order:10;text-align:left}
  #lb-counter{font-size:.75rem}
  .lb-btn{padding:5px 9px;font-size:.75rem}
  #lb-nav-left,#lb-nav-right{width:38px;height:52px;font-size:1.4rem}
  #lb-nav-left{left:4px}#lb-nav-right{right:4px}
  #lb-img{max-width:96vw;max-height:76vh}
  #bulk-bar{padding:8px 12px;gap:6px;font-size:.8rem;bottom:16px}
  .bar-btn{padding:5px 10px;font-size:.76rem}
  #bulk-count{font-size:.8rem;min-width:60px}
  .modal-box{padding:18px 16px;margin:12px}
}
</style>
</head>
<body>
<header>
  __BACK__
  <span class="logo">🖼 Forge Gallery</span>
  <div class="breadcrumb">__BREADCRUMB__</div>
  <div class="view-toggle">
    <button class="view-btn" data-v="grid" onclick="setView('grid')" title="Kafelki">&#9638;</button>
    <button class="view-btn" data-v="list" onclick="setView('list')" title="Lista">&#9776;</button>
  </div>
  <button class="btn primary" onclick="openMkdir()">&#128193;+ Nowy folder</button>
  <a href="/logout" class="btn" style="color:#94a3b8">&#10155; Wyloguj</a>
</header>
<main>
__DIRS_SECTION__
__IMGS_SECTION__
__EMPTY__
</main>

<div id="lightbox" onclick="closeLb()">
  <div id="lb-toolbar" onclick="event.stopPropagation()">
    <button class="lb-btn" onclick="closeLb()">&#10005; Zamknij</button>
    <span id="lb-filename"></span>
    <span id="lb-counter"></span>
    <a id="lb-open" class="lb-btn" href="#" target="_blank">&#10696; Nowe okno</a>
    <a id="lb-dl" class="lb-btn" href="#" download>&#11015; Pobierz</a>
    <button class="lb-btn del" id="lb-del-btn">&#128465; Usuń</button>
  </div>
  <button id="lb-nav-left" onclick="event.stopPropagation();nav(-1)">&#8249;</button>
  <img id="lb-img" src="" onclick="event.stopPropagation()">
  <button id="lb-nav-right" onclick="event.stopPropagation();nav(1)">&#8250;</button>
</div>

<div id="bulk-bar">
  <span id="bulk-count">0 zaznaczonych</span>
  <button class="bar-btn" onclick="selectAll()">&#9745; Wszystkie</button>
  <button class="bar-btn" onclick="clearSel()">&#10005; Odznacz</button>
  <button class="bar-btn move" onclick="openMove()">&#10145; Przenieś</button>
  <button class="bar-btn del" onclick="bulkDelete()">&#128465; Usuń</button>
</div>

<div id="mkdir-modal" class="modal" onclick="if(event.target===this)closeMkdir()">
  <div class="modal-box">
    <h3>&#128193; Nowy folder</h3>
    <input id="mkdir-name" class="modal-input" type="text" placeholder="Nazwa folderu..."
           onkeydown="if(event.key==='Enter')mkdirSubmit()">
    <div class="modal-btns">
      <button class="btn" onclick="closeMkdir()">Anuluj</button>
      <button class="btn primary" onclick="mkdirSubmit()">&#10003; Utwórz</button>
    </div>
  </div>
</div>

<div id="move-modal" class="modal" onclick="if(event.target===this)closeMove()">
  <div class="modal-box">
    <h3>&#10145; Przenieś do folderu</h3>
    <div id="move-folder-list" class="folder-list"><div class="no-dirs">Ładowanie...</div></div>
    <div class="modal-btns">
      <button class="btn" onclick="closeMove()">Anuluj</button>
      <button class="btn primary" onclick="moveSubmit()">&#10003; Przenieś</button>
    </div>
  </div>
</div>

<div id="movedir-modal" class="modal" onclick="if(event.target===this)closeMovedir()">
  <div class="modal-box">
    <h3>&#128193;&#10145; Przenieś folder</h3>
    <div id="movedir-src-label" style="font-size:.8rem;color:#64748b;margin-bottom:8px"></div>
    <div id="movedir-folder-list" class="folder-list"><div class="no-dirs">Ładowanie...</div></div>
    <div class="modal-btns">
      <button class="btn" onclick="closeMovedir()">Anuluj</button>
      <button class="btn primary" onclick="moveDirSubmit()">&#10003; Przenieś</button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
var imgs = __IMAGES_JSON__;
var cur  = 0;
var CUR_PATH = __CUR_PATH__;
var _lastCbIdx = null;
var _shiftOnCb  = false;

/* --- Widok --- */
function getView(){ return localStorage.getItem('fg_view') || 'grid'; }
function setView(v){
  localStorage.setItem('fg_view', v);
  applyView();
}
function applyView(){
  var v = getView();
  var ic = document.getElementById('imgs-container');
  if(ic) ic.className = v === 'list' ? 'imgs-list' : 'imgs-grid';
  var dc = document.getElementById('dirs-container');
  if(dc) dc.className = v === 'list' ? 'dirs-list' : 'dirs-grid';
  document.querySelectorAll('.view-btn').forEach(function(b){
    b.classList.toggle('active', b.dataset.v === v);
  });
}

/* --- Lightbox --- */
function openLb(idx){ cur=idx; updLb(); document.getElementById('lightbox').classList.add('open'); document.body.style.overflow='hidden'; }
function closeLb(){ document.getElementById('lightbox').classList.remove('open'); document.body.style.overflow=''; }
function nav(d){ cur=(cur+d+imgs.length)%imgs.length; updLb(); }
function updLb(){
  var url=imgs[cur], name=decodeURIComponent(url.split('/').pop());
  document.getElementById('lb-img').src=url;
  document.getElementById('lb-filename').textContent=name;
  document.getElementById('lb-counter').textContent=(cur+1)+' / '+imgs.length;
  document.getElementById('lb-open').href=url;
  document.getElementById('lb-dl').href=url;
  document.getElementById('lb-dl').download=name;
  document.getElementById('lb-del-btn').onclick=function(){ delUrl(imgs[cur]); };
}

document.addEventListener('click', function(e){
  var card=e.target.closest('.img-card');
  if(!card) return;
  if(e.target.closest('button,label,a,input')) return;
  var idx=parseInt(card.dataset.idx,10);
  if(!isNaN(idx)) openLb(idx);
});

/* mousedown odpala przed togglem — zapamiętaj czy shift był wciśnięty na checkboxie */
document.addEventListener('mousedown', function(e){
  _shiftOnCb = !!(e.shiftKey && e.target.closest('.cb-wrap'));
});

document.addEventListener('change', function(e){
  if(!e.target.classList.contains('img-cb')) return;
  var allCbs=[].slice.call(document.querySelectorAll('.img-cb'));
  var idx=allCbs.indexOf(e.target);
  if(_shiftOnCb && _lastCbIdx!==null && idx!==_lastCbIdx){
    var nst=e.target.checked;
    var from=Math.min(_lastCbIdx,idx), to=Math.max(_lastCbIdx,idx);
    for(var i=from;i<=to;i++){
      allCbs[i].checked=nst;
      allCbs[i].closest('.img-card').classList.toggle('selected',nst);
    }
    _lastCbIdx=idx;
  } else {
    e.target.closest('.img-card').classList.toggle('selected', e.target.checked);
    _lastCbIdx=idx;
  }
  _shiftOnCb=false;
  updateBar();
});

/* --- Delete --- */
function dlImg(url,name){ var a=document.createElement('a'); a.href=url; a.download=name; a.click(); }

function delUrl(url){
  var name=decodeURIComponent(url.split('/').pop());
  if(!confirm('Usunąć plik?\\n'+name)) return;
  fetch('/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:[url]})})
    .then(function(r){return r.json();}).then(function(d){
      if(d.ok){
        toast('Usunięto: '+name,'ok');
        var c=document.querySelector('.img-card[data-url="'+url+'"]');
        if(c) c.remove();
        var i=imgs.indexOf(url); if(i>-1) imgs.splice(i,1);
        updImgCount();
        if(document.getElementById('lightbox').classList.contains('open')){
          if(!imgs.length){ closeLb(); return; }
          cur=Math.min(cur,imgs.length-1); updLb();
        }
      } else toast('Błąd: '+d.error,'err');
    }).catch(function(){toast('Błąd połączenia','err');});
}

function updImgCount(){
  var el=document.getElementById('img-count');
  if(el) el.textContent=imgs.length+' obrazów';
}

/* --- Bulk --- */
function getSel(){ return [].slice.call(document.querySelectorAll('.img-cb:checked')).map(function(cb){return cb.dataset.url;}); }
function updateBar(){
  var n=document.querySelectorAll('.img-cb:checked').length;
  document.getElementById('bulk-count').textContent=n+' zaznaczonych';
  document.getElementById('bulk-bar').classList.toggle('show',n>0);
}
function selectAll(){ document.querySelectorAll('.img-cb').forEach(function(cb){ cb.checked=true; cb.closest('.img-card').classList.add('selected'); }); updateBar(); }
function clearSel(){ document.querySelectorAll('.img-cb').forEach(function(cb){ cb.checked=false; cb.closest('.img-card').classList.remove('selected'); }); updateBar(); _lastCbIdx=null; }

function bulkDelete(){
  var paths=getSel(); if(!paths.length) return;
  if(!confirm('Usunąć '+paths.length+' plików?\\nOperacja nieodwracalna.')) return;
  fetch('/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:paths})})
    .then(function(r){return r.json();}).then(function(d){
      if(d.ok){
        paths.forEach(function(url){
          var c=document.querySelector('.img-card[data-url="'+url+'"]');
          if(c) c.remove();
          var i=imgs.indexOf(url); if(i>-1) imgs.splice(i,1);
        });
        updImgCount(); toast('Usunięto '+d.deleted+' plików','ok'); clearSel();
      } else toast('Błąd: '+d.error,'err');
    }).catch(function(){toast('Błąd połączenia','err');});
}

/* --- Mkdir --- */
function openMkdir(){
  document.getElementById('mkdir-modal').classList.add('open');
  document.getElementById('mkdir-name').value='';
  setTimeout(function(){document.getElementById('mkdir-name').focus();},80);
}
function closeMkdir(){ document.getElementById('mkdir-modal').classList.remove('open'); }
function mkdirSubmit(){
  var name=document.getElementById('mkdir-name').value.trim();
  if(!name || name.indexOf('/')!==-1 || name.indexOf('..')!==-1) return toast('Nieprawidłowa nazwa','err');
  fetch('/mkdir',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:CUR_PATH+name})})
    .then(function(r){return r.json();}).then(function(d){
      if(d.ok){ toast('Folder utworzony: '+name,'ok'); closeMkdir(); setTimeout(function(){location.reload();},600); }
      else toast('Błąd: '+d.error,'err');
    }).catch(function(){toast('Błąd połączenia','err');});
}

/* --- Move --- */
var _moveSel = null;
function openMove(){
  var paths=getSel(); if(!paths.length) return;
  document.getElementById('move-modal').classList.add('open');
  _moveSel=null;
  var list=document.getElementById('move-folder-list');
  list.innerHTML='<div class="no-dirs">Ładowanie...</div>';
  fetch('/api/dirs').then(function(r){return r.json();}).then(function(d){
    list.innerHTML='';
    if(!d.dirs||!d.dirs.length){
      var empty=document.createElement('div'); empty.className='no-dirs'; empty.textContent='Brak folderów'; list.appendChild(empty); return;
    }
    d.dirs.forEach(function(f){
      var el=document.createElement('div');
      el.className='folder-opt'; el.dataset.path=f;
      el.onclick=function(){ selFolder(this); };
      el.textContent='📂 '+f;
      list.appendChild(el);
    });
  }).catch(function(){
    list.innerHTML=''; var err=document.createElement('div'); err.className='no-dirs'; err.textContent='Błąd ładowania'; list.appendChild(err);
  });
}
function closeMove(){ document.getElementById('move-modal').classList.remove('open'); _moveSel=null; }
function selFolder(el){
  document.querySelectorAll('.folder-opt').forEach(function(o){o.classList.remove('sel');});
  el.classList.add('sel'); _moveSel=el.dataset.path;
}
function moveSubmit(){
  var paths=getSel();
  if(!paths.length) return toast('Zaznacz obrazy','err');
  if(!_moveSel) return toast('Wybierz folder docelowy','err');
  fetch('/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:paths,target:_moveSel})})
    .then(function(r){return r.json();}).then(function(d){
      if(d.ok){
        toast('Przeniesiono '+d.moved+' plików → '+_moveSel,'ok');
        closeMove(); clearSel(); setTimeout(function(){location.reload();},800);
      } else toast('Błąd: '+d.error,'err');
    }).catch(function(){toast('Błąd połączenia','err');});
}

/* --- MoveDir --- */
var _moveDirSrc = null, _moveDirSel = null;
function openMovedir(srcPath){
  _moveDirSrc=srcPath; _moveDirSel=null;
  document.getElementById('movedir-src-label').textContent='&#128193; '+srcPath;
  document.getElementById('movedir-modal').classList.add('open');
  var list=document.getElementById('movedir-folder-list');
  list.innerHTML='<div class="no-dirs">Ładowanie...</div>';
  fetch('/api/dirs').then(function(r){return r.json();}).then(function(d){
    list.innerHTML='';
    var root=document.createElement('div');
    root.className='folder-opt'; root.dataset.path='';
    root.onclick=function(){selMovedirFolder(this);}
    root.textContent='&#128202; / (katalog główny)';
    list.appendChild(root);
    (d.dirs||[]).forEach(function(f){
      if(f===srcPath||f.startsWith(srcPath+'/')) return;
      var el=document.createElement('div');
      el.className='folder-opt'; el.dataset.path=f;
      el.onclick=function(){selMovedirFolder(this);}
      el.textContent='&#128194; '+f;
      list.appendChild(el);
    });
  }).catch(function(){list.innerHTML='<div class="no-dirs">Błąd ładowania</div>';});
}
function closeMovedir(){ document.getElementById('movedir-modal').classList.remove('open'); _moveDirSrc=null; _moveDirSel=null; }
function selMovedirFolder(el){
  document.querySelectorAll('#movedir-folder-list .folder-opt').forEach(function(o){o.classList.remove('sel');});
  el.classList.add('sel'); _moveDirSel=el.dataset.path;
}
function moveDirSubmit(){
  if(!_moveDirSrc) return;
  if(_moveDirSel===null) return toast('Wybierz folder docelowy','err');
  fetch('/movedir',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({src:_moveDirSrc,target:_moveDirSel})})
    .then(function(r){return r.json();}).then(function(d){
      if(d.ok){ toast('Przeniesiono folder → '+(_moveDirSel||'/'),'ok'); closeMovedir(); setTimeout(function(){location.reload();},800); }
      else toast('Błąd: '+d.error,'err');
    }).catch(function(){toast('Błąd połączenia','err');});
}

/* --- Toast --- */
function toast(msg,type){
  var t=document.getElementById('toast');
  t.textContent=msg; t.className='show '+(type||'');
  clearTimeout(t._t); t._t=setTimeout(function(){t.className='';},3200);
}

/* --- Klawiatura --- */
document.addEventListener('keydown',function(e){
  if(document.getElementById('lightbox').classList.contains('open')){
    if(e.key==='Escape') closeLb();
    if(e.key==='ArrowLeft') nav(-1);
    if(e.key==='ArrowRight') nav(1);
    return;
  }
  if(document.getElementById('mkdir-modal').classList.contains('open') && e.key==='Escape'){ closeMkdir(); return; }
  if(document.getElementById('move-modal').classList.contains('open') && e.key==='Escape'){ closeMove(); return; }
  if(document.getElementById('movedir-modal').classList.contains('open') && e.key==='Escape'){ closeMovedir(); return; }
});

applyView();
</script>
</body>
</html>"""


class GalleryHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _get_session(self):
        cookie = self.headers.get('Cookie', '')
        for part in cookie.split(';'):
            part = part.strip()
            if part.startswith(COOKIE_NAME + '='):
                return part[len(COOKIE_NAME)+1:]
        return None

    def _is_auth(self): return self._get_session() in SESSIONS

    def _redirect(self, location, code=302):
        self.send_response(code)
        self.send_header('Location', location)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _show_login(self, error=''):
        err_html = f'<div class="err">{html.escape(error)}</div>' if error else ''
        data = LOGIN_PAGE.replace('{ERROR}', err_html).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/logout':
            token = self._get_session()
            if token: SESSIONS.discard(token)
            self.send_response(302)
            self.send_header('Location', '/login')
            self.send_header('Set-Cookie', f'{COOKIE_NAME}=; Max-Age=0; Path=/')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        if self.path in ('/', '/login') and not self._is_auth():
            self._show_login(); return
        if not self._is_auth():
            self._redirect('/login'); return

        # API: lista folderów do modala "Przenieś"
        if self.path == '/api/dirs':
            dirs = []
            def walk(d, rel, depth=0):
                if depth > 2: return
                try:
                    for e in sorted(d.iterdir()):
                        if e.is_dir():
                            r = (rel + '/' + e.name).strip('/')
                            dirs.append(r)
                            walk(e, r, depth + 1)
                except: pass
            walk(OUTPUTS_DIR, '')
            self._json({'dirs': dirs})
            return

        rel  = unquote(self.path.split('?')[0]).lstrip('/')
        full = OUTPUTS_DIR / rel
        if not full.exists():
            self.send_error(404); return
        if full.is_dir():
            self.serve_dir(full, rel)
        else:
            self.serve_file(full)

    def do_POST(self):
        if self.path == '/login':
            length = int(self.headers.get('Content-Length', 0))
            body   = self.rfile.read(length).decode('utf-8', errors='replace')
            params = parse_qs(body)
            username = params.get('username', [''])[0].strip()
            password = params.get('password', [''])[0]
            pw_hash  = hashlib.sha256(password.encode()).hexdigest()
            if USERS.get(username) == pw_hash:
                token = secrets.token_hex(32)
                SESSIONS.add(token)
                self.send_response(302)
                self.send_header('Location', '/')
                self.send_header('Set-Cookie',
                    f'{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Lax')
                self.send_header('Content-Length', '0')
                self.end_headers()
            else:
                self._show_login('Nieprawidłowy login lub hasło')
            return

        if not self._is_auth():
            self.send_error(403); return

        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        root   = str(OUTPUTS_DIR.resolve())

        if self.path == '/delete':
            try:
                data  = json.loads(body)
                paths = data.get('paths') or [data['path']]
                deleted, errors = 0, []
                for p in paths:
                    rel    = unquote(p).lstrip('/')
                    target = (OUTPUTS_DIR / rel).resolve()
                    if not str(target).startswith(root):
                        errors.append(f'invalid: {rel}'); continue
                    if not target.is_file():
                        errors.append(f'missing: {rel}'); continue
                    target.unlink()
                    deleted += 1
                self._json({'ok': True, 'deleted': deleted, 'errors': errors})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return

        if self.path == '/mkdir':
            try:
                data = json.loads(body)
                path = data.get('path', '').strip().strip('/')
                if not path or '..' in path:
                    self._json({'ok': False, 'error': 'Nieprawidłowa ścieżka'}); return
                target = (OUTPUTS_DIR / path).resolve()
                if not str(target).startswith(root):
                    self._json({'ok': False, 'error': 'Poza zakresem'}); return
                target.mkdir(parents=True, exist_ok=True)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return

        if self.path == '/move':
            try:
                data       = json.loads(body)
                paths      = data.get('paths', [])
                target_rel = data.get('target', '').strip().strip('/')
                if not target_rel or '..' in target_rel:
                    self._json({'ok': False, 'error': 'Nieprawidłowy folder docelowy'}); return
                target_dir = (OUTPUTS_DIR / target_rel).resolve()
                if not str(target_dir).startswith(root):
                    self._json({'ok': False, 'error': 'Poza zakresem'}); return
                target_dir.mkdir(parents=True, exist_ok=True)
                moved, errors = 0, []
                for p in paths:
                    rel = unquote(p).lstrip('/')
                    src = (OUTPUTS_DIR / rel).resolve()
                    if not str(src).startswith(root) or not src.is_file():
                        errors.append(rel); continue
                    dst = target_dir / src.name
                    if dst.exists():
                        stem, sfx = src.stem, src.suffix
                        i = 1
                        while dst.exists():
                            dst = target_dir / f'{stem}_{i}{sfx}'
                            i += 1
                    shutil.move(str(src), str(dst))
                    moved += 1
                self._json({'ok': True, 'moved': moved, 'errors': errors})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return

        if self.path == '/movedir':
            try:
                data    = json.loads(body)
                src_rel = data.get('src', '').strip().strip('/')
                dst_rel = data.get('target', '').strip().strip('/')
                if not src_rel or '..' in src_rel or '..' in dst_rel:
                    self._json({'ok': False, 'error': 'Nieprawidłowa ścieżka'}); return
                src = (OUTPUTS_DIR / src_rel).resolve()
                if not str(src).startswith(root) or not src.is_dir():
                    self._json({'ok': False, 'error': 'Katalog źródłowy nie istnieje'}); return
                dst_dir = (OUTPUTS_DIR / dst_rel).resolve() if dst_rel else OUTPUTS_DIR.resolve()
                if not str(dst_dir).startswith(root):
                    self._json({'ok': False, 'error': 'Poza zakresem'}); return
                if str(dst_dir) == str(src.parent):
                    self._json({'ok': False, 'error': 'Folder już jest w tym miejscu'}); return
                if str(dst_dir).startswith(str(src) + '/') or str(dst_dir) == str(src):
                    self._json({'ok': False, 'error': 'Nie można przenieść do własnego podkatalogu'}); return
                dst_dir.mkdir(parents=True, exist_ok=True)
                target = dst_dir / src.name
                if target.exists():
                    self._json({'ok': False, 'error': f'Folder "{src.name}" już istnieje w docelowym katalogu'}); return
                shutil.move(str(src), str(target))
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return

        self.send_error(404)

    def serve_file(self, path):
        mime, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime or 'application/octet-stream')
        self.send_header('Content-Length', len(data))
        self.send_header('Cache-Control', 'public, max-age=3600')
        self.end_headers()
        self.wfile.write(data)

    def serve_dir(self, dir_path, rel):
        entries = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name))
        dirs    = [e for e in entries if e.is_dir()]
        images  = [e for e in entries if e.is_file() and e.suffix.lower() in IMAGE_EXTS]

        # Breadcrumb
        parts = [p for p in rel.split('/') if p]
        bc = '<a href="/">&#128193; outputs</a>'
        cp = ''
        for p in parts:
            cp += '/' + p
            bc += f' / <a href="{cp}/">{html.escape(p)}</a>'

        # Back button
        back = ''
        if parts:
            parent = ('/' + '/'.join(parts[:-1]) + '/').replace('//', '/')
            back = f'<a href="{parent}" class="btn">← Wróć</a>'

        # Ścieżka bieżąca dla JS
        cur_path = (rel.strip('/') + '/') if rel.strip('/') else ''

        # Dirs HTML
        dirs_html = ''
        for d in dirs:
            link    = ('/' + rel + '/' + quote(d.name) + '/').replace('//', '/')
            dir_rel = (rel + '/' + d.name).strip('/')
            try:
                sub      = list(d.iterdir())
                cnt      = sum(1 for f in sub if f.is_file() and f.suffix.lower() in IMAGE_EXTS)
                prev_imgs = sorted(
                    [f for f in sub if f.is_file() and f.suffix.lower() in IMAGE_EXTS],
                    key=lambda x: x.stat().st_mtime, reverse=True
                )[:5]
                prev_html = ''.join(
                    '<img src="{}" alt="" loading="lazy">'.format(
                        ('/' + rel + '/' + quote(d.name) + '/' + quote(p.name)).replace('//', '/')
                    ) for p in prev_imgs
                )
            except:
                cnt, prev_html = 0, ''
            dirs_html += (
                f'<div class="dir-card" onclick="location.href=\'{link}\'">'
                f'<button class="dir-move-btn" onclick="event.stopPropagation();openMovedir(\'{dir_rel}\')">&#10145; Przenieś</button>'
                f'<div class="dir-main">'
                f'<div class="dir-icon">&#128194;</div>'
                f'<div class="dir-info">'
                f'<div class="dir-name">{html.escape(d.name)}</div>'
                f'<div class="dir-count">{cnt} obrazów</div>'
                f'</div></div>'
                f'<div class="dir-previews">{prev_html}</div>'
                f'</div>'
            )

        # Images HTML
        imgs_html = ''
        img_urls  = []
        for img in images:
            url  = ('/' + rel + '/' + quote(img.name)).replace('//', '/')
            img_urls.append(url)
            idx  = len(img_urls) - 1
            kb   = img.stat().st_size // 1024
            name = html.escape(img.name)
            imgs_html += (
                f'<div class="img-card" data-url="{url}" data-idx="{idx}">'
                f'<label class="cb-wrap">'
                f'<input type="checkbox" class="img-cb" data-url="{url}">'
                f'</label>'
                f'<img src="{url}" loading="lazy" alt="{name}">'
                f'<div class="img-overlay">'
                f'<div class="img-name">{name}</div>'
                f'<div class="img-meta">{kb} KB</div>'
                f'<div class="img-actions">'
                f'<button onclick="window.open(\'{url}\',\'_blank\')" title="Nowe okno">&#10696; Okno</button>'
                f'<button onclick="dlImg(\'{url}\',\'{name}\')" title="Pobierz">&#11015; Pobierz</button>'
                f'<button class="del" onclick="delUrl(\'{url}\')" title="Usuń">&#128465; Usuń</button>'
                f'</div></div></div>'
            )

        dirs_sec = (
            f'<div class="section-title"><span>Foldery ({len(dirs)})</span></div>'
            f'<div class="dirs-grid" id="dirs-container">{dirs_html}</div>'
        ) if dirs_html else ''
        imgs_sec = (
            f'<div class="section-title"><span id="img-count">{len(images)} obrazów</span></div>'
            f'<div class="imgs-grid" id="imgs-container">{imgs_html}</div>'
        ) if imgs_html else ''
        empty = '<div class="empty">&#128193; Pusty folder</div>' if not dirs_html and not imgs_html else ''

        page = (HTML_TEMPLATE
            .replace('__BACK__',         back)
            .replace('__BREADCRUMB__',   bc)
            .replace('__DIRS_SECTION__', dirs_sec)
            .replace('__IMGS_SECTION__', imgs_sec)
            .replace('__EMPTY__',        empty)
            .replace('__IMAGES_JSON__',  json.dumps(img_urls))
            .replace('__CUR_PATH__',     json.dumps(cur_path))
        )
        data = page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), GalleryHandler)
    print(f'Forge Gallery → http://0.0.0.0:{PORT}')
    server.serve_forever()
