from flask import Flask, request, redirect, session, render_template_string
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "final_full_facebook"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png','jpg','jpeg','gif','mp4','mov','avi','mkv','webm'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASS = "admin123"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_db():
    db = sqlite3.connect("facebook.db")
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, password TEXT, is_blocked INTEGER DEFAULT 0)")
    db.execute("CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, user_id INTEGER, text TEXT, media TEXT, media_type TEXT, time TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER, text TEXT, time TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS likes (id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, sender_id INTEGER, receiver_id INTEGER, text TEXT, time TEXT)")
    db.commit()
    admin = db.execute("SELECT * FROM users WHERE email=?", (ADMIN_EMAIL,)).fetchone()
    if not admin:
        db.execute("INSERT INTO users (name,email,password) VALUES (?,?,?)", ("Admin", ADMIN_EMAIL, ADMIN_PASS))
        db.commit()

init_db()

BASE_HTML = """
<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'>
<style>
body{font-family:Arial;background:#f0f2f5;margin:0}
.navbar{background:#1877f2;padding:10px;color:white;display:flex;justify-content:space-between;position:sticky;top:0;z-index:100}
.card{background:white;padding:15px;margin:10px auto;max-width:550px;border-radius:8px;box-shadow:0 1px 2px rgba(0,0,0,0.2)}
input,textarea{width:100%;padding:10px;margin:5px 0;box-sizing:border-box}
button{background:#1877f2;color:white;border:none;padding:10px;width:100%;border-radius:5px;cursor:pointer}
a{color:#1877f2;text-decoration:none}
video,img{max-width:100%;border-radius:8px;margin-top:10px}
.action-bar{display:flex;justify-content:space-around;border-top:1px solid #ddd;margin-top:10px;padding-top:10px}
.action-bar a{font-weight:bold;color:#65676b}
.danger{background:#ff4757}
.success{background:#2ed573}
</style></head>
<body>
<div class='navbar'><b>My Social</b><div>
{% if session.get('user_id') %}
<a href='/home' style='color:white;margin:5px'>Home</a>
<a href='/messenger' style='color:white;margin:5px'>Chat</a>
{% if session.get('is_admin') %}<a href='/admin' style='color:yellow;margin:5px'><b>ADMIN</b></a>{% endif %}
<a href='/logout' style='color:white;margin:5px'>Logout</a>
{% endif %}
</div></div>
{{ content | safe }}
</body></html>
"""

@app.route("/", methods=["GET","POST"])
def index():
    if request.method=="POST":
        email=request.form['email']; password=request.form['password']
        db=get_db(); user=db.execute("SELECT * FROM users WHERE email=? AND password=?",(email,password)).fetchone()
        if user:
            if user['is_blocked'] == 1:
                return render_template_string(BASE_HTML.replace("{{ content | safe }}","<div class='card'><p style='color:red'>তোমার একাউন্ট Block করা হয়েছে!</p><a href='/'>Back</a></div>"))
            session["user_id"]=user["id"]; session["name"]=user["name"]
            session["is_admin"] = True if user["email"] == ADMIN_EMAIL else False
            return redirect("/home")
        return render_template_string(BASE_HTML.replace("{{ content | safe }}","<div class='card'><p style='color:red'>ভুল ইমেইল বা পাসওয়ার্ড</p><a href='/'>আবার চেষ্টা করো</a></div>"))
    return render_template_string(BASE_HTML.replace("{{ content | safe }}","""
    <div class='card'><h2>Login</h2><form method='post'><input name='email' placeholder='Email' required><input name='password' type='password' placeholder='Password' required><button>Login</button></form><p><a href='/signup'>Create new account</a></p><p style='font-size:11px;color:gray'>Admin: admin@gmail.com / admin123</p></div>
    """))

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method=="POST":
        db=get_db()
        try:
            db.execute("INSERT INTO users (name,email,password) VALUES (?,?,?)",(request.form['name'],request.form['email'],request.form['password'])); db.commit()
            return redirect("/")
        except: return "Email exists <a href='/signup'>Try again</a>"
    return render_template_string(BASE_HTML.replace("{{ content | safe }}","""
    <div class='card'><h2>Signup</h2><form method='post'><input name='name' placeholder='Full Name' required><input name='email' placeholder='Email' required><input name='password' type='password' placeholder='Password' required><button>Signup</button></form></div>
    """))

@app.route("/home", methods=["GET","POST"])
def home():
    if "user_id" not in session: return redirect("/")
    db=get_db()
    if request.method=="POST":
        text=request.form.get('text',''); file=request.files.get('file'); filename=None; mtype=None
        if file and file.filename and allowed_file(file.filename):
            filename=secure_filename(datetime.now().strftime("%Y%m%d%H%M%S_")+file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            mtype='video' if filename.rsplit('.',1)[1].lower() in ['mp4','mov','avi','mkv','webm'] else 'image'
        db.execute("INSERT INTO posts (user_id,text,media,media_type,time) VALUES (?,?,?,?,?)",(session["user_id"],text,filename,mtype,datetime.now().strftime("%Y-%m-%d %H:%M"))); db.commit()
        return redirect("/home")

    posts=db.execute("SELECT posts.*, users.name FROM posts JOIN users ON posts.user_id=users.id ORDER BY posts.id DESC").fetchall()
    html=f"""<div class='card'><h3>Create Post</h3><form method='post' enctype='multipart/form-data'><textarea name='text' placeholder="What's on your mind?"></textarea><input type='file' name='file' accept='image/*,video/*'><button>Post</button></form></div>"""
    for p in posts:
        media_html=""
        if p['media']:
            if p['media_type']=='video':
                media_html=f"<video controls><source src='/static/uploads/{p['media']}'></video>"
            else:
                media_html=f"<img src='/static/uploads/{p['media']}'>"
        like_count = db.execute("SELECT COUNT(*) as c FROM likes WHERE post_id=?", (p['id'],)).fetchone()['c']
        liked = db.execute("SELECT * FROM likes WHERE post_id=? AND user_id=?", (p['id'], session['user_id'])).fetchone()
        like_text = f"Unlike ({like_count})" if liked else f"Like ({like_count})"
        comments=db.execute("SELECT comments.*, users.name FROM comments JOIN users ON comments.user_id=users.id WHERE post_id=?", (p['id'],)).fetchall()
        cmt_html="".join([f"<p style='background:#f0f2f5;padding:5px;border-radius:10px;margin:3px'><b>{c['name']}:</b> {c['text']}</p>" for c in comments])
        html+=f"""<div class='card'><h3>{p['name']}</h3><p>{p['text']}</p>{media_html}
        <div class='action-bar'>
            <a href='/like/{p['id']}'>{like_text}</a>
            <a href='#'>Comment ({len(comments)})</a>
            <a href='/share/{p['id']}'>Share</a>
        </div>
        <hr>{cmt_html}
        <form method='post' action='/comment/{p['id']}' style='display:flex;gap:5px'><input name='text' placeholder='Write a comment' required><button style='width:80px'>Post</button></form>
        </div>"""
    return render_template_string(BASE_HTML.replace("{{ content | safe }}",html))

@app.route("/like/<int:post_id>")
def like(post_id):
    if "user_id" not in session: return redirect("/")
    db=get_db()
    liked = db.execute("SELECT * FROM likes WHERE post_id=? AND user_id=?", (post_id, session['user_id'])).fetchone()
    if liked:
        db.execute("DELETE FROM likes WHERE post_id=? AND user_id=?", (post_id, session['user_id']))
    else:
        db.execute("INSERT INTO likes (post_id, user_id) VALUES (?,?)", (post_id, session['user_id']))
    db.commit()
    return redirect("/home")

@app.route("/share/<int:post_id>")
def share(post_id):
    if "user_id" not in session: return redirect("/")
    db=get_db()
    post = db.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    if post:
        db.execute("INSERT INTO posts (user_id,text,media,media_type,time) VALUES (?,?,?,?,?)",(session["user_id"], f"Shared: {post['text']}", post['media'], post['media_type'], datetime.now().strftime("%Y-%m-%d %H:%M")))
        db.commit()
    return redirect("/home")

@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):
    if "user_id" not in session: return redirect("/")
    db=get_db(); db.execute("INSERT INTO comments (post_id, user_id, text, time) VALUES (?,?,?,?)",(post_id, session["user_id"], request.form['text'], datetime.now().strftime("%H:%M"))); db.commit()
    return redirect("/home")

@app.route("/messenger", methods=["GET","POST"])
def messenger():
    if "user_id" not in session: return redirect("/")
    db=get_db(); all_users=db.execute("SELECT * FROM users WHERE is_blocked=0").fetchall(); selected=request.args.get("user")
    chat_html=""
    if selected:
        other=db.execute("SELECT * FROM users WHERE id=?",(selected,)).fetchone()
        if request.method=="POST":
            db.execute("INSERT INTO messages (sender_id, receiver_id, text, time) VALUES (?,?,?,?)",(session["user_id"], selected, request.form['msg'], datetime.now().strftime("%H:%M"))); db.commit()
        msgs=db.execute("SELECT * FROM messages WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?) ORDER BY id ASC",(session["user_id"],selected,selected,session["user_id"])).fetchall()
        chat_html=f"<div class='card'><h3>Chat with {other['name']}</h3><div style='height:350px;overflow-y:auto;border:1px solid #ddd;padding:10px'>"
        for m in msgs:
            align="right" if m["sender_id"]==session["user_id"] else "left"
            color="#0084ff" if m["sender_id"]==session["user_id"] else "#f0f0f0"
            tcolor="white" if m["sender_id"]==session["user_id"] else "black"
            chat_html+=f"<div style='text-align:{align};margin:5px'><span style='background:{color};color:{tcolor};padding:7px 12px;border-radius:15px;display:inline-block'>{m['text']}</span></div>"
        chat_html+=f"</div><form method='post' style='display:flex;gap:5px;margin-top:10px;'><input name='msg' placeholder='Type a message' required style='flex:1'><button style='width:70px'>Send</button></form></div>"
    else:
        chat_html="<div class='card'><p>Select a friend to start chatting</p></div>"
    list_html="<div class='card'><h3>Messenger - All Friends</h3>"
    for u in all_users:
        if u["id"]!=session["user_id"]:
            list_html+=f"<p><a href='/messenger?user={u['id']}'><b>{u['name']}</b> - Chat Now</a></p>"
    list_html+="</div>"
    return render_template_string(BASE_HTML.replace("{{ content | safe }}",list_html+chat_html))

@app.route("/admin")
def admin_panel():
    if not session.get('is_admin'): return "তুমি Admin না! <a href='/home'>Home</a>"
    db=get_db(); users=db.execute("SELECT * FROM users").fetchall(); posts=db.execute("SELECT posts.*, users.name FROM posts JOIN users ON posts.user_id=users.id ORDER BY posts.id DESC").fetchall()
    u_html="<div class='card'><h2>Admin Panel</h2>"
    for u in users:
        if u['email']!= ADMIN_EMAIL:
            status = "🔴 Blocked" if u['is_blocked'] else "🟢 Active"
            btn = f"<a href='/admin/unblock/{u['id']}'><button class='success' style='width:90px;padding:5px'>Unblock</button></a>" if u['is_blocked'] else f"<a href='/admin/block/{u['id']}'><button class='danger' style='width:90px;padding:5px'>Block</button></a>"
            u_html+=f"<p>{u['name']} ({u['email']}) - {status} {btn}</p>"
    u_html+="</div><div class='card'><h2>All Posts</h2>"
    for p in posts:
        u_html+=f"<p><b>{p['name']}:</b> {p['text'][:40]} <a href='/admin/delete_post/{p['id']}'><button class='danger' style='width:100px;padding:5px'>Delete</button></a></p>"
    u_html+="</div>"
    return render_template_string(BASE_HTML.replace("{{ content | safe }}",u_html))

@app.route("/admin/block/<int:uid>")
def block_user(uid):
    if not session.get('is_admin'): return redirect("/home")
    db=get_db(); db.execute("UPDATE users SET is_blocked=1 WHERE id=?",(uid,)); db.commit(); return redirect("/admin")
@app.route("/admin/unblock/<int:uid>")
def unblock_user(uid):
    if not session.get('is_admin'): return redirect("/home")
    db=get_db(); db.execute("UPDATE users SET is_blocked=0 WHERE id=?",(uid,)); db.commit(); return redirect("/admin")
@app.route("/admin/delete_post/<int:pid>")
def delete_post(pid):
    if not session.get('is_admin'): return redirect("/home")
    db=get_db(); post=db.execute("SELECT media FROM posts WHERE id=?",(pid,)).fetchone()
    if post and post['media']:
        try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], post['media']))
        except: pass
    db.execute("DELETE FROM posts WHERE id=?",(pid,)); db.execute("DELETE FROM comments WHERE post_id=?",(pid,)); db.execute("DELETE FROM likes WHERE post_id=?",(pid,)); db.commit(); return redirect("/admin")

@app.route("/logout")
def logout(): session.clear(); return redirect("/")

if __name__=="__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)