#!/usr/bin/env python3
"""Forge Gallery — przeglądarka, zarządzanie i organizacja outputs Forge"""

import html, json, mimetypes, os, secrets, hashlib, shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, quote, parse_qs

OUTPUTS_DIR = Path(os.environ.get('FG_OUTPUTS_DIR', '/home/bartek/forge/outputs'))
PORT        = int(os.environ.get('FG_PORT', '7861'))
PORTAL_URL  = os.environ.get('FG_PORTAL_URL', 'https://images.ebartnet.pl')
PORTAL_KEY  = os.environ.get('FG_PORTAL_KEY', '')
IMAGE_EXTS  = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
VIDEO_EXTS  = {'.mp4', '.webm', '.mov'}
MEDIA_EXTS  = IMAGE_EXTS | VIDEO_EXTS

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
.dir-delete-btn{position:absolute;top:6px;right:80px;background:#3f1515;border:1px solid #ef4444;color:#fca5a5;border-radius:6px;padding:3px 8px;font-size:.72rem;cursor:pointer;opacity:0;transition:opacity .15s;z-index:2;line-height:1.4}
.dir-card:hover .dir-delete-btn{opacity:1}
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
#imgs-container.imgs-grid .img-card img,#imgs-container.imgs-grid .img-card video{width:100%;height:100%;object-fit:cover;display:block}
.vid-badge{position:absolute;top:8px;right:8px;background:rgba(0,0,0,.65);color:#fff;font-size:.85rem;border-radius:5px;padding:2px 6px;z-index:2;pointer-events:none}
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
#imgs-container.imgs-list .img-card img,#imgs-container.imgs-list .img-card video{width:50px;height:50px;object-fit:cover;border-radius:5px;flex-shrink:0;order:1}
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
.img-actions button.pub{background:rgba(99,102,241,.75)}.img-actions button.pub:hover{background:rgba(99,102,241,1)}
.img-actions button.unpub{background:rgba(239,68,68,.25)}.img-actions button.unpub:hover{background:rgba(239,68,68,.55)}
.img-cb{width:18px;height:18px;cursor:pointer;accent-color:#3b82f6;display:block}
.empty{color:#475569;text-align:center;padding:60px;font-size:1.1rem}

/* Lightbox */
#lightbox{display:none;position:fixed;inset:0;background:rgba(0,0,0,.93);z-index:1000;flex-direction:column}
#lightbox.open{display:flex}
#lb-body{display:flex;flex:1;min-height:0;align-items:center;justify-content:center;gap:0}
#lb-img-wrap{display:flex;flex:1;align-items:center;justify-content:center;min-width:0;height:100%;padding:8px}
#lb-img{max-width:100%;max-height:100%;object-fit:contain;border-radius:4px;box-shadow:0 0 60px rgba(0,0,0,.8)}
#lb-meta{width:320px;flex-shrink:0;height:100%;overflow-y:auto;background:#0f172a;border-left:1px solid #1e3a5f;padding:16px;box-sizing:border-box;display:flex;flex-direction:column;gap:12px}
#lb-meta .meta-section{background:#1e293b;border:1px solid #1e3a5f;border-radius:8px;padding:12px}
#lb-meta .meta-label{font-size:.68rem;font-weight:700;color:#3b82f6;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px}
#lb-meta .meta-value{font-size:.8rem;color:#e2e8f0;line-height:1.5;word-break:break-word;white-space:pre-wrap}
#lb-meta .meta-value.mono{font-family:monospace;font-size:.75rem;color:#94a3b8}
#lb-meta .meta-tag{display:inline-block;background:#1e3a5f;color:#7dd3fc;font-size:.68rem;padding:2px 7px;border-radius:4px;margin:2px 2px 0 0}
#lb-meta .meta-params{display:grid;grid-template-columns:1fr 1fr;gap:6px}
#lb-meta .meta-param{background:#0f172a;border:1px solid #1e3a5f;border-radius:6px;padding:6px 8px}
#lb-meta .meta-param-k{font-size:.65rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em}
#lb-meta .meta-param-v{font-size:.82rem;color:#e2e8f0;font-weight:600;margin-top:2px}
#lb-meta-empty{font-size:.8rem;color:#475569;text-align:center;padding:24px 0}
#lb-copy-btn{font-size:.7rem;background:transparent;border:1px solid #334155;color:#64748b;padding:3px 8px;border-radius:5px;cursor:pointer;float:right;margin-top:-2px}
#lb-copy-btn:hover{color:#e2e8f0;border-color:#64748b}
#lb-toolbar{position:fixed;top:0;left:0;right:0;display:flex;align-items:center;padding:10px 16px;background:rgba(15,23,42,.9);backdrop-filter:blur(8px);z-index:1001;gap:8px;flex-wrap:wrap}
#lb-filename{flex:1;font-size:.85rem;color:#94a3b8;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#lb-seed{font-size:.78rem;color:#fbbf24;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
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
  #lb-meta{display:none}
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
    <span id="lb-seed"></span>
    <span id="lb-counter"></span>
    <a id="lb-open" class="lb-btn" href="#" target="_blank">&#10696; Nowe okno</a>
    <a id="lb-dl" class="lb-btn" href="#" download>&#11015; Pobierz</a>
    <button class="lb-btn" id="lb-pub-btn" style="background:#4f46e5" onclick="publishImg(imgs[cur])">&#9889; Opublikuj</button>
    <button class="lb-btn del" id="lb-del-btn">&#128465; Usuń</button>
  </div>
  <div id="lb-body" onclick="event.stopPropagation()">
    <div id="lb-img-wrap">
      <button id="lb-nav-left" onclick="event.stopPropagation();nav(-1)" style="position:absolute;left:8px;z-index:10">&#8249;</button>
      <img id="lb-img" src="" onclick="event.stopPropagation()">
      <video id="lb-vid" src="" controls autoplay loop style="display:none;max-width:100%;max-height:100%;object-fit:contain;border-radius:4px;box-shadow:0 0 60px rgba(0,0,0,.8)" onclick="event.stopPropagation()"></video>
      <button id="lb-nav-right" onclick="event.stopPropagation();nav(1)" style="position:absolute;right:328px;z-index:10">&#8250;</button>
    </div>
    <div id="lb-meta"><div id="lb-meta-empty">&#128247; Ładowanie metadanych...</div></div>
  </div>
</div>

<div id="bulk-bar">
  <span id="bulk-count">0 zaznaczonych</span>
  <button class="bar-btn" onclick="selectAll()">&#9745; Wszystkie</button>
  <button class="bar-btn" onclick="clearSel()">&#10005; Odznacz</button>
  <button class="bar-btn move" onclick="openMove()">&#10145; Przenieś</button>
  <button class="bar-btn del" onclick="bulkDelete()">&#128465; Usuń</button>
</div>

<div id="publish-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:9999;align-items:center;justify-content:center;">
  <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:22px 24px;max-width:360px;width:90%;">
    <div style="font-size:16px;font-weight:700;color:#e2e8f0;margin:0 0 8px;">&#9889; Opublikuj zdjęcie</div>
    <div style="color:#94a3b8;font-size:13px;margin:0 0 18px;">Zdjęcie będzie widoczne na <b>images.ebartnet.pl</b></div>
    <div style="display:flex;flex-direction:column;gap:8px;">
      <button onclick="doPublish(false)" style="padding:10px;background:#6366f1;border:none;border-radius:7px;color:#fff;cursor:pointer;font-size:14px;font-weight:600;">&#128444; Opublikuj normalnie</button>
      <button onclick="doPublish(true)" style="padding:10px;background:#7f1d1d;border:1px solid #991b1b;border-radius:7px;color:#fca5a5;cursor:pointer;font-size:14px;font-weight:600;">&#128286; Opublikuj jako XXX</button>
      <button onclick="document.getElementById(\'publish-modal\').style.display=\'none\'" style="padding:8px;background:transparent;border:1px solid #334155;border-radius:7px;color:#94a3b8;cursor:pointer;font-size:13px;">Anuluj</button>
    </div>
    <input type="hidden" id="pub-url">
  </div>
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
function isVideoUrl(u){ return /\.(mp4|webm|mov)$/i.test(u); }
function updLb(){
  var url=imgs[cur], name=decodeURIComponent(url.split('/').pop());
  var imgEl=document.getElementById('lb-img'), vidEl=document.getElementById('lb-vid');
  if(isVideoUrl(url)){
    imgEl.style.display='none'; imgEl.src='';
    vidEl.style.display=''; vidEl.src=url;
  } else {
    vidEl.style.display='none'; vidEl.pause(); vidEl.src='';
    imgEl.style.display=''; imgEl.src=url;
  }
  document.getElementById('lb-filename').textContent=name;
  var sm=name.match(/_s(\d+)\./);
  document.getElementById('lb-seed').textContent=sm?'Seed: '+sm[1]:'';
  document.getElementById('lb-counter').textContent=(cur+1)+' / '+imgs.length;
  document.getElementById('lb-open').href=url;
  document.getElementById('lb-dl').href=url;
  document.getElementById('lb-dl').download=name;
  document.getElementById('lb-del-btn').onclick=function(){ delUrl(imgs[cur]); };
  /* panel metadanych */
  var meta=document.getElementById('lb-meta');
  meta.innerHTML='<div id="lb-meta-empty">&#128247; Ładowanie...</div>';
  fetch('/api/genphoto-meta?path='+encodeURIComponent(url))
    .then(function(r){return r.json();})
    .then(function(d){
      if(!d.ok||!d.raw){meta.innerHTML='<div id="lb-meta-empty" style="color:#475569;padding:24px 0;text-align:center">Brak metadanych</div>';return;}
      var h='';
      /* model */
      if(d.model){
        h+='<div class="meta-section"><div class="meta-label">Checkpoint</div>';
        h+='<span class="meta-tag">'+esc(d.model)+'</span></div>';
      }
      /* prompt */
      if(d.positive){
        h+='<div class="meta-section"><div class="meta-label">Prompt';
        h+='<button id="lb-copy-btn" onclick="navigator.clipboard.writeText('+JSON.stringify(d.positive)+')">&#128203; Kopiuj</button></div>';
        h+='<div class="meta-value">'+esc(d.positive)+'</div></div>';
      }
      /* negative */
      if(d.negative){
        h+='<div class="meta-section"><div class="meta-label">Negative prompt</div>';
        h+='<div class="meta-value" style="color:#94a3b8">'+esc(d.negative)+'</div></div>';
      }
      /* parametry */
      var params=[];
      if(d.cfg_scale||d.cfg)  params.push(['CFG Scale',d.cfg_scale||d.cfg]);
      if(d.steps)              params.push(['Steps',d.steps]);
      if(d.sampler)            params.push(['Sampler',d.sampler]);
      if(d.scheduler)          params.push(['Scheduler',d.scheduler]);
      if(d.seed)               params.push(['Seed',d.seed]);
      if(d.size)               params.push(['Size',d.size]);
      if(params.length){
        h+='<div class="meta-section"><div class="meta-label">Parametry</div><div class="meta-params">';
        params.forEach(function(p){
          h+='<div class="meta-param"><div class="meta-param-k">'+esc(p[0])+'</div><div class="meta-param-v">'+esc(String(p[1]))+'</div></div>';
        });
        h+='</div></div>';
      }
      meta.innerHTML=h;
    })
    .catch(function(){meta.innerHTML='<div id="lb-meta-empty" style="color:#475569;padding:24px 0;text-align:center">Błąd odczytu metadanych</div>';});
}
function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}

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
function gpLoad(url, btn) {
  var orig = btn.textContent;
  btn.textContent = '...'; btn.disabled = true;
  fetch('/api/genphoto-meta?path=' + encodeURIComponent(url))
    .then(function(r){return r.json();})
    .then(function(d){
      btn.textContent = orig; btn.disabled = false;
      var p = new URLSearchParams();
      if(d.positive)  p.set('positive',  d.positive);
      if(d.negative)  p.set('negative',  d.negative);
      if(d.model)     p.set('model',     d.model);
      if(d.sampler)   p.set('sampler',   d.sampler);
      if(d.scheduler) p.set('scheduler', d.scheduler);
      if(d.steps)     p.set('steps',     d.steps);
      if(d.cfg_scale) p.set('cfg_scale', d.cfg_scale);
      if(d.width)     p.set('width',     d.width);
      if(d.height)    p.set('height',    d.height);
      if(d.seed)      p.set('seed',      d.seed);
      window.open('https://genphoto.ebartnet.pl/?' + p.toString(), '_blank');
    })
    .catch(function(){btn.textContent=orig;btn.disabled=false;});
}
function dlImg(url,name){ var a=document.createElement('a'); a.href=url; a.download=name; a.click(); }

function publishImg(url) {
  document.getElementById('pub-url').value = url;
  document.getElementById('publish-modal').style.display = 'flex';
}

function unpublishImg(url) {
  if (!confirm('Cofnąć publikację tego zdjęcia z images.ebartnet.pl?')) return;
  var toastEl = document.createElement('div');
  toastEl.style.cssText='position:fixed;bottom:20px;right:20px;background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:10px 16px;border-radius:8px;font-size:13px;z-index:9999;';
  toastEl.textContent = '⏳ Usuwanie…';
  document.body.appendChild(toastEl);
  fetch('/api/unpublish-from-portal', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({url: url})
  }).then(function(r){return r.json();}).then(function(d){
    if(d.ok){
      toastEl.textContent = '✓ Zdjęcie usunięte z portalu';
      toastEl.style.borderColor = '#059669';
    } else {
      toastEl.textContent = '✗ Błąd: ' + (d.error || 'nieznany');
      toastEl.style.borderColor = '#ef4444';
    }
    setTimeout(function(){ toastEl.remove(); }, 4000);
  }).catch(function(){ toastEl.textContent='✗ Błąd sieci'; setTimeout(function(){ toastEl.remove(); },4000); });
}

function doPublish(isXxx) {
  var url = document.getElementById('pub-url').value;
  document.getElementById('publish-modal').style.display = 'none';
  var toastEl = document.createElement('div');
  toastEl.style.cssText='position:fixed;bottom:20px;right:20px;background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:10px 16px;border-radius:8px;font-size:13px;z-index:9999;';
  toastEl.textContent = '⏳ Publikowanie…';
  document.body.appendChild(toastEl);
  fetch('/api/publish-to-portal', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({url: url, is_xxx: isXxx})
  }).then(function(r){return r.json();}).then(function(d){
    if(d.ok){
      toastEl.textContent = '✓ Opublikowano! ';
      var lnk = document.createElement('a');
      lnk.href = 'https://images.ebartnet.pl' + d.url;
      lnk.target = '_blank';
      lnk.style.color = '#a5b4fc';
      lnk.textContent = 'Zobacz →';
      toastEl.appendChild(lnk);
      toastEl.style.borderColor = '#059669';
    } else {
      toastEl.textContent = '✗ Błąd: ' + d.error;
      toastEl.style.borderColor = '#ef4444';
    }
    setTimeout(function(){ toastEl.remove(); }, 6000);
  }).catch(function(e){ toastEl.textContent='✗ Błąd sieci'; setTimeout(function(){ toastEl.remove(); },4000); });
}

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
  if(el) el.textContent=imgs.length+' plików';
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
function deleteDir(dirRel){
  if(!confirm('Usunąć folder "'+dirRel+'" i całą jego zawartość? Operacja nieodwracalna.')) return;
  fetch('/deletedir',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:dirRel})})
  .then(function(r){return r.json();}).then(function(d){
    if(d.ok){ toast('Usunięto: '+dirRel,'ok'); setTimeout(function(){location.reload();},800); }
    else toast('Błąd: '+(d.error||'?'),'err');
  });
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
        if self.path.startswith('/api/genphoto-meta'):
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            rel_path = qs.get('path', [''])[0]
            if not rel_path:
                self._json({'ok': False, 'error': 'brak path'}); return
            full = OUTPUTS_DIR / unquote(rel_path).lstrip('/')
            try:
                from PIL import Image as _PI
                with _PI.open(full) as im:
                    params_str = im.info.get('parameters', '')
                result = {'ok': bool(params_str), 'raw': params_str}
                if params_str:
                    lines = params_str.split('\n')
                    result['positive'] = lines[0].strip()
                    neg = next((l.replace('Negative prompt:','').strip() for l in lines if l.startswith('Negative prompt:')), '')
                    result['negative'] = neg
                    meta_line = next((l for l in lines if 'Steps:' in l), '')
                    for kv in meta_line.split(','):
                        kv = kv.strip()
                        if ': ' in kv:
                            k, v = kv.split(': ', 1)
                            result[k.strip().lower().replace(' ','_')] = v.strip()
                self._json(result)
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return

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

        def safe_rel(rel):
            """True jeśli rel jest bezpieczną ścieżką względną (bez .. i /)."""
            p = Path(rel)
            return rel and not p.is_absolute() and '..' not in p.parts

        def safe_path(rel):
            """Zwraca Path do pliku/folderu w OUTPUTS_DIR (przez symlinki też)."""
            return OUTPUTS_DIR / rel

        if self.path == '/delete':
            try:
                data  = json.loads(body)
                paths = data.get('paths') or [data['path']]
                deleted, errors = 0, []
                for p in paths:
                    rel = unquote(p).lstrip('/')
                    if not safe_rel(rel):
                        errors.append(f'invalid: {rel}'); continue
                    target = safe_path(rel)
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
                if not safe_rel(path):
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
                if not safe_rel(target_rel):
                    self._json({'ok': False, 'error': 'Nieprawidłowy folder docelowy'}); return
                target_dir = (OUTPUTS_DIR / target_rel).resolve()
                if not str(target_dir).startswith(root):
                    self._json({'ok': False, 'error': 'Poza zakresem'}); return
                target_dir.mkdir(parents=True, exist_ok=True)
                moved, errors = 0, []
                for p in paths:
                    rel = unquote(p).lstrip('/')
                    if not safe_rel(rel):
                        errors.append(rel); continue
                    src = safe_path(rel)
                    if not src.is_file():
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
                if not safe_rel(src_rel) or '..' in dst_rel:
                    self._json({'ok': False, 'error': 'Nieprawidłowa ścieżka'}); return
                src = safe_path(src_rel)
                if not src.is_dir():
                    self._json({'ok': False, 'error': 'Katalog źródłowy nie istnieje'}); return
                dst_dir = (OUTPUTS_DIR / dst_rel).resolve() if dst_rel else OUTPUTS_DIR.resolve()
                if not str(dst_dir).startswith(root):
                    self._json({'ok': False, 'error': 'Poza zakresem'}); return
                src_resolved = src.resolve()
                if str(dst_dir) == str(src_resolved.parent):
                    self._json({'ok': False, 'error': 'Folder już jest w tym miejscu'}); return
                if str(dst_dir).startswith(str(src_resolved) + '/') or str(dst_dir) == str(src_resolved):
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

        if self.path == '/deletedir':
            try:
                data = json.loads(body)
                rel  = data.get('path', '').strip().strip('/')
                if not safe_rel(rel):
                    self._json({'ok': False, 'error': 'Nieprawidłowa ścieżka'}); return
                target = safe_path(rel)
                if not target.is_dir():
                    self._json({'ok': False, 'error': 'Katalog nie istnieje'}); return
                shutil.rmtree(target)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return

        if self.path == '/api/publish-to-portal':
            try:
                import uuid as _uuid, urllib.request as _ureq
                from urllib.parse import unquote as _unquote
                data = json.loads(body)
                rel_url = _unquote(data.get('url', '')).lstrip('/')
                is_xxx  = 1 if data.get('is_xxx') else 0
                if not rel_url:
                    self._json({'ok': False, 'error': 'Brak url'}); return

                # Zabezpieczenie przed path traversal (bez resolve — obsługuje symlinki)
                if '..' in rel_url.split('/') or rel_url.startswith('/'):
                    self._json({'ok': False, 'error': 'Niedozwolona ścieżka'}); return
                full = OUTPUTS_DIR / rel_url
                if not full.exists():
                    self._json({'ok': False, 'error': 'Plik nie istnieje'}); return
                file_bytes = full.read_bytes()

                # Odczytaj metadane z PNG przez PIL
                meta = {}
                try:
                    import io as _io, json as _json
                    from PIL import Image as _PI
                    with _PI.open(_io.BytesIO(file_bytes)) as im:
                        params_str = im.info.get('parameters', '')
                        comfy_str  = im.info.get('prompt', '')
                        meta['width'], meta['height'] = im.size

                    if params_str:
                        # Format Forge/SD: tekst w chunk 'parameters'
                        lines = params_str.split('\n')
                        meta['positive'] = lines[0].strip()
                        meta['negative'] = next(
                            (l.replace('Negative prompt:', '').strip()
                             for l in lines if l.startswith('Negative prompt:')), '')
                        meta_line = next((l for l in lines if 'Steps:' in l), '')
                        for kv in meta_line.split(','):
                            kv = kv.strip()
                            if ': ' in kv:
                                k, v = kv.split(': ', 1)
                                meta[k.strip().lower().replace(' ', '_')] = v.strip()

                    elif comfy_str:
                        # Format ComfyUI: JSON workflow w chunk 'prompt'
                        wf = _json.loads(comfy_str)
                        for node in wf.values():
                            ct = node.get('class_type', '')
                            inp = node.get('inputs', {})
                            if ct == 'KSampler':
                                meta.setdefault('seed',    str(inp.get('seed', '')))
                                meta.setdefault('steps',   str(inp.get('steps', '')))
                                meta.setdefault('cfg_scale', str(inp.get('cfg', '')))
                                meta.setdefault('sampler', inp.get('sampler_name', ''))
                                meta.setdefault('scheduler', inp.get('scheduler', ''))
                            elif ct == 'CLIPTextEncode' and not isinstance(inp.get('text'), list):
                                txt = inp.get('text', '').strip()
                                if txt and 'positive' not in meta:
                                    meta['positive'] = txt
                                elif txt and 'negative' not in meta:
                                    meta['negative'] = txt
                            elif ct in ('CheckpointLoaderSimple', 'UNETLoader') and 'model' not in meta:
                                meta['model'] = inp.get('ckpt_name', inp.get('unet_name', ''))
                except Exception:
                    pass  # bez PIL — wysyłamy bez metadanych

                # Buduj multipart/form-data
                boundary = _uuid.uuid4().hex
                fields = {
                    'positive':     meta.get('positive', ''),
                    'negative':     meta.get('negative', ''),
                    'model':        meta.get('model', ''),
                    'sampler':      meta.get('sampler', ''),
                    'scheduler':    meta.get('schedule_type', meta.get('scheduler', '')),
                    'steps':        meta.get('steps', ''),
                    'cfg':          meta.get('cfg_scale', ''),
                    'width':        str(meta.get('width', '')),
                    'height':       str(meta.get('height', '')),
                    'seed':         meta.get('seed', ''),
                    'source':       'forge-gallery',
                    'source_path':  rel_url,
                    'is_xxx':       str(is_xxx),
                }
                parts = bytearray()
                for k, v in fields.items():
                    parts += (
                        f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
                    ).encode()
                # (file_bytes pobrane wyżej z dysku)
                parts += (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                    f'filename="image.png"\r\nContent-Type: image/png\r\n\r\n'
                ).encode() + file_bytes + f'\r\n--{boundary}--\r\n'.encode()

                portal_url = PORTAL_URL.rstrip('/') + '/api/publish'
                req = _ureq.Request(
                    portal_url, data=bytes(parts),
                    headers={
                        'Content-Type': f'multipart/form-data; boundary={boundary}',
                        'X-Api-Key': PORTAL_KEY,
                    }, method='POST'
                )
                with _ureq.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                self._json({'ok': True, 'url': result.get('url', ''), 'uuid': result.get('uuid', '')})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return

        if self.path == '/api/unpublish-from-portal':
            try:
                import urllib.request as _ureq
                from urllib.parse import unquote as _unquote
                data = json.loads(body)
                rel_url = _unquote(data.get('url', '')).lstrip('/')
                if not rel_url:
                    self._json({'ok': False, 'error': 'Brak url'}); return
                portal_url = PORTAL_URL.rstrip('/') + '/api/unpublish'
                payload = json.dumps({'source_path': rel_url}).encode()
                req = _ureq.Request(portal_url, data=payload, headers={
                    'Content-Type': 'application/json',
                    'X-Api-Key': PORTAL_KEY,
                }, method='POST')
                with _ureq.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read())
                self._json(result)
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
        images  = [e for e in entries if e.is_file() and e.suffix.lower() in MEDIA_EXTS]

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
                cnt      = sum(1 for f in sub if f.is_file() and f.suffix.lower() in MEDIA_EXTS)
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
                f'<button class="dir-delete-btn" onclick="event.stopPropagation();deleteDir(\'{dir_rel}\')">&#10005; Usuń</button>'
                f'<button class="dir-move-btn" onclick="event.stopPropagation();openMovedir(\'{dir_rel}\')">&#10145; Przenieś</button>'
                f'<div class="dir-main">'
                f'<div class="dir-icon">&#128194;</div>'
                f'<div class="dir-info">'
                f'<div class="dir-name">{html.escape(d.name)}</div>'
                f'<div class="dir-count">{cnt} plików</div>'
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
            is_video = img.suffix.lower() in VIDEO_EXTS
            media_html = (
                f'<video src="{url}" muted preload="metadata" playsinline></video><div class="vid-badge">&#9654;</div>'
                if is_video else
                f'<img src="{url}" loading="lazy" alt="{name}">'
            )
            imgs_html += (
                f'<div class="img-card" data-url="{url}" data-idx="{idx}">'
                f'<label class="cb-wrap">'
                f'<input type="checkbox" class="img-cb" data-url="{url}">'
                f'</label>'
                f'{media_html}'
                f'<div class="img-overlay">'
                f'<div class="img-name">{name}</div>'
                f'<div class="img-meta">{kb} KB</div>'
                f'<div class="img-actions">'
                f'<button onclick="window.open(\'{url}\',\'_blank\')" title="Nowe okno">&#10696; Okno</button>'
                f'<button onclick="dlImg(\'{url}\',\'{name}\')" title="Pobierz">&#11015; Pobierz</button>'
                f'<button onclick="gpLoad(\'{url}\', this)" style="background:rgba(59,130,246,.7);" title="Wczytaj do GenPhoto">&#8594; GP</button>'
                f'<button class="pub" onclick="publishImg(\'{url}\')" title="Opublikuj na portalu">&#9889; Opublikuj</button>'
                f'<button class="unpub" onclick="unpublishImg(\'{url}\')" title="Cofnij publikację">&#8617; Cofnij pub.</button>'
                f'<button class="del" onclick="delUrl(\'{url}\')" title="Usuń">&#128465; Usuń</button>'
                f'</div></div></div>'
            )

        dirs_sec = (
            f'<div class="section-title"><span>Foldery ({len(dirs)})</span></div>'
            f'<div class="dirs-grid" id="dirs-container">{dirs_html}</div>'
        ) if dirs_html else ''
        imgs_sec = (
            f'<div class="section-title"><span id="img-count">{len(images)} plik&oacute;w</span></div>'
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
