import requests
from flask import Flask, render_template_string, request, send_from_directory, jsonify

app = Flask(__name__)

OL_SEARCH = "https://openlibrary.org/search.json"
OL_COVER = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
OL_BOOK = "https://openlibrary.org{key}"
TIMEOUT = 10

HEADERS = {"User-Agent": "Bookworm/1.0 (OpenClaw)"}


def ol_search(query, limit=10):
    params = {
        "q": query,
        "limit": limit,
        "fields": "key,title,author_name,cover_i,first_publish_year,ratings_average,ratings_count",
    }
    r = requests.get(OL_SEARCH, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    docs = r.json().get("docs", [])
    results = []
    for doc in docs:
        cover_id = doc.get("cover_i")
        authors = doc.get("author_name", [])
        rating = doc.get("ratings_average")
        rating_str = f"{rating:.1f} ({doc.get('ratings_count', 0):,} ratings)" if rating else ""
        results.append({
            "title": doc.get("title", "Unknown"),
            "author": authors[0] if authors else "Unknown",
            "cover": OL_COVER.format(cover_id=cover_id) if cover_id else "",
            "url": OL_BOOK.format(key=doc.get("key", "")),
            "year": doc.get("first_publish_year", ""),
            "rating": rating_str,
        })
    return results


def get_related_via_openlibrary(title, author):
    """Find related books via Open Library subjects API."""
    query = (title + " " + author).strip()
    r = requests.get(
        OL_SEARCH,
        params={"q": query, "fields": "key,title,subject,author_name,cover_i", "limit": 1},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    docs = r.json().get("docs", [])
    if not docs:
        return []

    doc = docs[0]
    subjects = doc.get("subject", [])
    skip = {"fiction", "english", "juvenile fiction", "nonfiction", "non-fiction"}
    chosen_subject = None
    for s in subjects:
        if s.lower() not in skip and len(s) > 3:
            chosen_subject = s
            break
    if not chosen_subject:
        return []

    subj_slug = chosen_subject.lower().replace(" ", "_").replace(",", "").replace("'", "")
    r2 = requests.get(
        f"https://openlibrary.org/subjects/{subj_slug}.json",
        params={"limit": 10},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    if r2.status_code != 200:
        return []

    works = r2.json().get("works", [])
    books = []
    seen_titles = set()
    for w in works:
        t = w.get("title", "").strip()
        if t.lower() == title.lower() or t.lower() in seen_titles:
            continue
        seen_titles.add(t.lower())
        authors = [a["name"] for a in w.get("authors", [])]
        cover_id = w.get("cover_id")
        ol_key = w.get("key", "")
        books.append({
            "title": t,
            "author": authors[0] if authors else "",
            "cover": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else "",
            "url": f"https://openlibrary.org{ol_key}" if ol_key else "",
        })
    return books


HOME_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bookworm</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="alternate icon" type="image/x-icon" href="/favicon.ico">
<link rel="apple-touch-icon" href="/favicon.ico">
<style>
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #1a1a1a; color: #e0e0e0; }
  h1 { margin-bottom: 4px; }
  form { margin: 20px 0; }
  input[type=text] { padding: 8px 12px; width: 300px; font-size: 16px; border: 1px solid #444; border-radius: 4px; background: #2a2a2a; color: #e0e0e0; }
  input[type=text]::placeholder { color: #666; }
  .search-wrap { display: inline-flex; align-items: center; position: relative; }
  .clear-btn { position: absolute; right: 8px; background: none; border: none; font-size: 16px; color: #666; cursor: pointer; padding: 0; line-height: 1; display: none; }
  .clear-btn:hover { color: #ccc; }
  button { padding: 8px 16px; font-size: 16px; cursor: pointer; border: 1px solid #555; border-radius: 4px; background: #2a2a2a; color: #e0e0e0; }
  button:hover { background: #333; }
  .card { display: flex; gap: 14px; padding: 12px; margin-bottom: 12px; background: #242424; border: 1px solid #333; border-radius: 6px; }
  .card img { width: 80px; height: auto; object-fit: contain; flex-shrink: 0; }
  .card-body { flex: 1; }
  .card-body h3 { margin: 0 0 4px; }
  .card-body h3 a { color: #4caf82; text-decoration: none; }
  .card-body h3 a:hover { text-decoration: underline; }
  .card-body p { margin: 2px 0; color: #999; }
  .toggle-btn { background: none; border: none; color: #4caf82; cursor: pointer; padding: 4px 0; font-size: 14px; }
  .toggle-btn:hover { text-decoration: underline; }
  .related-box { margin: 8px 0 0 94px; }
  .related-box .mini { display: flex; gap: 10px; align-items: center; padding: 6px 0; border-top: 1px solid #333; }
  .related-box .mini img { width: 40px; height: auto; }
  .related-box .mini a { color: #4caf82; text-decoration: none; font-size: 14px; }
  .no-results { color: #666; margin-top: 20px; }
  .autocomplete-dropdown { position: absolute; top: 100%; left: 0; width: 340px; background: #2a2a2a; border: 1px solid #444; border-top: none; border-radius: 0 0 4px 4px; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
  .autocomplete-dropdown .ac-item { padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #333; }
  .autocomplete-dropdown .ac-item:last-child { border-bottom: none; }
  .autocomplete-dropdown .ac-item:hover, .autocomplete-dropdown .ac-item.selected { background: #1e3a2f; }
  .autocomplete-dropdown .ac-title { font-size: 14px; font-weight: 500; color: #e0e0e0; }
  .autocomplete-dropdown .ac-author { font-size: 12px; color: #888; margin-top: 1px; }
</style>
</head>
<body>
<h1>🐛 Bookworm</h1>
<form action="/search" method="get">
  <div class="search-wrap">
    <input type="text" name="q" id="searchInput" placeholder="Title, author, or ISBN" value="{{ query }}" oninput="onSearchInput()" onkeydown="onSearchKeydown(event)" autocomplete="off">
    <button type="button" class="clear-btn" id="clearBtn" onclick="clearSearch()" title="Clear">&#x2715;</button>
    <div class="autocomplete-dropdown" id="acDropdown" style="display:none;"></div>
  </div>
  <button type="submit">Search</button>
</form>
{% if results is not none %}
  {% if results %}
    {% for book in results %}
    <div class="card">
      {% if book.cover %}<img src="{{ book.cover }}" alt="">{% endif %}
      <div class="card-body">
        <h3><a href="{{ book.url }}" target="_blank">{{ book.title }}</a></h3>
        <p>{{ book.author }}{% if book.year %} · {{ book.year }}{% endif %}</p>
        {% if book.rating %}<p style="font-size:13px; color:#777;">⭐ {{ book.rating }}</p>{% endif %}
      </div>
    </div>
    {% endfor %}
  {% else %}
    <p class="no-results">No results found.</p>
  {% endif %}
{% endif %}
<script>
var acTimer = null;
var acSelected = -1;
var acItems = [];

function clearSearch() {
  var input = document.getElementById('searchInput');
  input.value = '';
  document.getElementById('clearBtn').style.display = 'none';
  hideDropdown();
  input.focus();
}

function toggleClear() {
  var input = document.getElementById('searchInput');
  document.getElementById('clearBtn').style.display = input.value ? 'block' : 'none';
}

function hideDropdown() {
  document.getElementById('acDropdown').style.display = 'none';
  acSelected = -1;
  acItems = [];
}

function onSearchInput() {
  toggleClear();
  var q = document.getElementById('searchInput').value;
  clearTimeout(acTimer);
  if (q.length < 3) { hideDropdown(); return; }
  acTimer = setTimeout(function() { fetchSuggestions(q); }, 300);
}

function fetchSuggestions(q) {
  fetch('/suggest?q=' + encodeURIComponent(q))
    .then(function(r) { return r.json(); })
    .then(function(items) {
      acItems = items;
      acSelected = -1;
      var drop = document.getElementById('acDropdown');
      if (!items.length) { drop.style.display = 'none'; return; }
      drop.innerHTML = '';
      items.forEach(function(item, i) {
        var div = document.createElement('div');
        div.className = 'ac-item';
        div.innerHTML = '<div class="ac-title">' + escHtml(item.title) + '</div><div class="ac-author">' + escHtml(item.author) + '</div>';
        div.addEventListener('mousedown', function(e) {
          e.preventDefault();
          selectSuggestion(i);
        });
        drop.appendChild(div);
      });
      drop.style.display = 'block';
    })
    .catch(function() { hideDropdown(); });
}

function selectSuggestion(i) {
  if (!acItems[i]) return;
  document.getElementById('searchInput').value = acItems[i].title;
  hideDropdown();
  document.querySelector('form').submit();
}

function onSearchKeydown(e) {
  var drop = document.getElementById('acDropdown');
  if (drop.style.display === 'none') return;
  var divs = drop.querySelectorAll('.ac-item');
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    acSelected = Math.min(acSelected + 1, divs.length - 1);
    divs.forEach(function(d, i) { d.classList.toggle('selected', i === acSelected); });
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    acSelected = Math.max(acSelected - 1, -1);
    divs.forEach(function(d, i) { d.classList.toggle('selected', i === acSelected); });
  } else if (e.key === 'Enter') {
    if (acSelected >= 0) { e.preventDefault(); selectSuggestion(acSelected); }
    else { hideDropdown(); }
  } else if (e.key === 'Escape') {
    hideDropdown();
  }
}

document.addEventListener('click', function(e) {
  if (!document.getElementById('searchInput').contains(e.target)) hideDropdown();
});

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

window.addEventListener('load', function() {
  if (window.performance && window.performance.navigation.type === window.performance.navigation.TYPE_RELOAD) {
    window.location.replace('/');
    return;
  }
  toggleClear();
  document.getElementById('searchInput').focus();
});
</script>
</body>
</html>"""

RELATED_FRAGMENT = """{% if books %}
{% for b in books %}
<div class="mini">
  {% if b.cover %}<img src="{{ b.cover }}" alt="">{% endif %}
  <a href="{{ b.url }}" target="_blank">{{ b.title }}{% if b.author %} — {{ b.author }}{% endif %}</a>
</div>
{% endfor %}
{% else %}
<em>No related books found.</em>
{% endif %}"""


@app.route("/suggest")
def suggest():
    q = request.args.get("q", "").strip()
    if len(q) < 3:
        return jsonify([])
    try:
        results = ol_search(q, limit=5)
    except Exception:
        results = []
    return jsonify([
        {"title": r["title"], "author": r["author"], "q": r["title"]}
        for r in results
    ])


@app.route("/favicon.ico")
def favicon_ico():
    return send_from_directory("static", "favicon.ico", mimetype="image/x-icon")


@app.route("/favicon.svg")
def favicon():
    return send_from_directory("static", "favicon.svg", mimetype="image/svg+xml")


@app.route("/")
def index():
    return render_template_string(HOME_PAGE, query="", results=None)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template_string(HOME_PAGE, query="", results=None)
    try:
        results = ol_search(q)
    except Exception:
        results = []
    return render_template_string(HOME_PAGE, query=q, results=results)


@app.route("/related")
def related():
    title = request.args.get("title", "").strip()
    author = request.args.get("author", "").strip()
    if not title:
        return "<em>No title provided.</em>"
    try:
        books = get_related_via_openlibrary(title, author)
    except Exception:
        books = []
    return render_template_string(RELATED_FRAGMENT, books=books)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
