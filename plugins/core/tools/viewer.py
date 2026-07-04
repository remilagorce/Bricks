#!/usr/bin/env python3
"""Bricks viewer — read-only live table for a workspace database.

Stdlib only. Run from the workspace root:  python3 tools/viewer.py
Options: --port 8765  --db bricks.db  --no-open

Serves a single dark-mode page on localhost with bottom tabs
(companies / people / messages), colored status chips, client-side filter,
and a 2-second auto-refresh. Read-only: it never writes to the database.
"""

import argparse
import json
import os
import sqlite3
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

TABLES = ("companies", "people", "messages", "seed_customers")

HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Bricks</title>
<style>
:root{color-scheme:dark}
body{margin:0;background:#121212;color:#ddd;font:13px -apple-system,system-ui,sans-serif;padding-bottom:48px}
header{display:flex;align-items:center;gap:12px;padding:10px 14px;border-bottom:1px solid #2a2a2a;position:sticky;top:0;background:#121212;z-index:2}
h1{font-size:14px;margin:0;font-weight:600}
h1 span{color:#ff5722}
#count{color:#888}
input{background:#1c1c1c;border:1px solid #333;color:#ddd;border-radius:6px;padding:5px 9px;width:220px;margin-left:auto}
table{border-collapse:collapse;width:100%}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid #222;max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
th{color:#888;font-weight:500;background:#121212}
.chip{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px}
.s-pending{background:#26262b;color:#9ca3af}.s-running{background:#3a2b0a;color:#fbbf24}
.s-done,.s-approved{background:#0d2f1b;color:#4ade80}.s-failed{background:#3b0d0d;color:#f87171}
.s-not_found{background:#26262b;color:#6b7280}.s-disqualified{background:#3b0d0d;color:#ef4444}
.s-draft{background:#12233f;color:#60a5fa}.s-sent{background:#0d2f2b;color:#2dd4bf}.s-new{background:#26262b;color:#9ca3af}
nav{position:fixed;bottom:0;left:0;right:0;display:flex;background:#171717;border-top:1px solid #2a2a2a}
nav button{background:none;border:none;color:#888;padding:12px 18px;font:inherit;cursor:pointer;border-top:2px solid transparent}
nav button.on{color:#fff;border-top-color:#ff5722}
</style></head><body>
<header><h1><span>&#9632;</span> Bricks</h1><span id="count"></span><input id="q" placeholder="Filtrer..."></header>
<div><table id="t"></table></div>
<nav>
<button data-t="companies" class="on">Entreprises</button>
<button data-t="people">Contacts</button>
<button data-t="messages">Messages</button>
<button data-t="seed_customers">Clients gagnés</button>
</nav>
<script>
let table='companies',q='',data=[];
document.querySelectorAll('nav button').forEach(function(b){
  b.onclick=function(){table=b.dataset.t;
    document.querySelectorAll('nav button').forEach(function(x){x.classList.toggle('on',x===b)});
    load()}});
document.getElementById('q').oninput=function(e){q=e.target.value.toLowerCase();render()};
async function load(){
  try{const r=await fetch('/data?table='+table);data=await r.json();render()}catch(e){}}
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;')}
function render(){
  const rows=data.filter(function(r){return !q||JSON.stringify(r).toLowerCase().includes(q)});
  document.getElementById('count').textContent=rows.length+' / '+data.length+' lignes';
  const t=document.getElementById('t');
  if(!rows.length){t.innerHTML='<tr><td style="color:#666;padding:24px">Aucune ligne</td></tr>';return}
  const cols=Object.keys(rows[0]);
  let h='<tr>'+cols.map(function(c){return '<th>'+c+'</th>'}).join('')+'</tr>';
  for(const r of rows){
    h+='<tr>'+cols.map(function(c){
      let v=r[c];if(v===null||v===undefined)v='';
      const s=esc(String(v));
      if((c==='status'||c.endsWith('_status'))&&s)
        return '<td><span class="chip s-'+s+'">'+s+'</span></td>';
      if(/^email_\d+$/.test(c)&&s){
        const i=s.indexOf(' — ');
        if(i>0)return '<td title="'+s+'"><span class="chip s-'+s.slice(0,i)+'">'+s.slice(0,i)+'</span> '+s.slice(i+3)+'</td>'}
      return '<td title="'+s+'">'+s+'</td>'}).join('')+'</tr>'}
  t.innerHTML=h}
setInterval(load,2000);load();
</script></body></html>"""


PEOPLE_QUERY = (
    "SELECT p.*, "
    + ", ".join(
        f"(SELECT m.status || ' — ' || COALESCE(m.subject, '') FROM messages m"
        f" WHERE m.person_id = p.id AND m.step = {s}) AS email_{s}"
        for s in (1, 2, 3)
    )
    + " FROM people p ORDER BY p.id DESC LIMIT 500"
)


def read_rows(db_path, table):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        if table == "people":
            query = PEOPLE_QUERY
        else:
            query = f"SELECT * FROM {table} ORDER BY id DESC LIMIT 500"
        rows = con.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


class Handler(BaseHTTPRequestHandler):
    db_path = "bricks.db"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML.encode("utf-8")
            content_type = "text/html; charset=utf-8"
        elif parsed.path == "/data":
            table = parse_qs(parsed.query).get("table", ["companies"])[0]
            if table not in TABLES:
                self.send_error(404, "unknown table")
                return
            try:
                body = json.dumps(
                    read_rows(self.db_path, table), ensure_ascii=False
                ).encode("utf-8")
            except sqlite3.Error as e:
                self.send_error(500, str(e))
                return
            content_type = "application/json; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Bricks read-only table viewer")
    parser.add_argument("--db", default="bricks.db")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(
            f"error: {args.db} not found — run the viewer from a workspace root",
            file=sys.stderr,
        )
        sys.exit(1)

    Handler.db_path = args.db
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Bricks viewer on {url} (Ctrl+C to stop)")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
