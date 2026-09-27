from flask import Flask, request, redirect, session, render_template_string
import sqlite3
import os
import re
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

try:
    import cloudinary
    import cloudinary.uploader
    IS_CLOUDINARY = True
except:
    IS_CLOUDINARY = False

app = Flask(__name__)
app.secret_key = "super_pro_final_v4_floating"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png','jpg','jpeg','gif','mp4','mov','avi','mkv','webm'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

if IS_CLOUDINARY and os.environ.get("CLOUDINARY_CLOUD_NAME"):
    cloudinary.config(
        cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
        api_key = os.environ.get("CLOUDINARY_API_KEY"),
        api_secret = os.environ.get("CLOUDINARY_API_SECRET")
    )

ADMIN_EMAIL = "mdbokkor44@gmail.com"
ADMIN_PASS = "admin123"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_db():
    if os.environ.get("DATABASE_URL"):
        import psycopg2
        url = os.environ.get("DATABASE_URL")
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)
    else:
        db = sqlite3.connect("facebook.db")
        db.row_factory = sqlite3.Row
        return db

def init_db():
    db = get_db()
    is_pg = os.environ.get("DATABASE_URL") is not None
    cur = db.cursor()
    if is_pg:
        cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name TEXT, email TEXT UNIQUE, password TEXT, is_blocked INTEGER DEFAULT 0, last_seen TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS posts (id SERIAL PRIMARY KEY, user_id INTEGER, text TEXT, media TEXT, media_type TEXT, time TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS comments (id SERIAL PRIMARY KEY, post_id INTEGER, user_id INTEGER, text TEXT, time TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS likes (id SERIAL PRIMARY KEY, post_id INTEGER, user_id INTEGER)")
        cur.execute("CREATE TABLE IF NOT EXISTS messages (id SERIAL PRIMARY KEY, sender_id INTEGER, receiver_id INTEGER, text TEXT, time TEXT)")
    else:
        cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, password TEXT, is_blocked INTEGER DEFAULT 0, last_seen TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, user_id INTEGER, text TEXT, media TEXT, media_type TEXT, time TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER, text TEXT, time TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS likes (id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER)")
        cur.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, sender_id INTEGER, receiver_id INTEGER, text TEXT, time TEXT)")
    db.commit()
    try:
        q = "SELECT * FROM users WHERE email=%s" if is_pg else "SELECT * FROM users WHERE email=?"
        cur.execute(q,(ADMIN_EMAIL,))
        if not cur.fetchone():
            q = "INSERT INTO users (name,email,password,last_seen) VALUES (%s,%s,%s,%s)" if is_pg else "INSERT INTO users (name,email,password,last_seen) VALUES (?,?,?,?)"
            cur.execute(q,("Admin", ADMIN_EMAIL, ADMIN_PASS, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            db.commit()
    except: pass
    cur.close(); db.close()

init_db()

@app.before_request
def update_last_seen():
    if session.get('user_id'):
        try:
            db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
            q = "UPDATE users SET last_seen=%s WHERE id=%s" if is_pg else "UPDATE users SET last_seen=? WHERE id=?"
            cur.execute(q,(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session['user_id']))
            db.commit(); cur.close(); db.close()
        except: pass

def is_online(last_seen_str):
    if not last_seen_str: return False
    try:
        last = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")
        return datetime.now() - last < timedelta(minutes=2)
    except: return False

BASE_HTML = """
<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'>
<style>
body{font-family:Arial;background:#f0f2f5;margin:0}
.navbar{background:#1877f2;padding:10px;color:white;display:flex;justify-content:space-between;position:sticky;top:0;z-index:100}
.card{background:white;padding:15px;margin:10px auto;max-width:600px;border-radius:8px;box-shadow:0 1px 2px rgba(0,0,0,0.2)}
input,textarea{width:100%;padding:10px;margin:5px 0;box-sizing:border-box}
button{background:#1877f2;color:white;border:none;padding:10px;width:100%;border-radius:5px;cursor:pointer}
a{color:#1877f2;text-decoration:none}
video,img{max-width:100%;border-radius:8px;margin-top:10px}
.action-bar{display:flex;justify-content:space-around;border-top:1px solid #ddd;margin-top:10px;padding-top:10px}
.danger{background:#ff4757}.success{background:#2ed573}
.dot{height:10px;width:10px;border-radius:50%;display:inline-block}
.online{background:#2ed573}.offline{background:#ccc}
.messenger-box{display:flex;max-width:900px;margin:10px auto;gap:10px}
.left-list{width:35%;background:white;border-radius:8px;padding:10px;height:80vh;overflow-y:auto}
.right-chat{width:65%}
.reel-card{max-width:350px;margin:15px auto;background:black;color:white;border-radius:15px;overflow:hidden}
.reel-card video{width:100%;height:500px;object-fit:cover}
.floating-msg{
  position: fixed; bottom: 25px; right: 25px; background: #0084ff; color: white;
  width: 60px; height: 60px; border-radius: 50%; display: flex;
  justify-content: center; align-items: center; font-size: 30px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.4); z-index: 9999; text-decoration: none;
  animation: pulse 2s infinite;
}
.floating-msg:hover{ background: #0066cc; transform: scale(1.1); }
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(0,132,255,0.7); }
  70% { box-shadow: 0 0 0 15px rgba(0,132,255,0); }
  100% { box-shadow: 0 0 0 0 rgba(0,132,255,0); }
}
</style></head><body>
<div class='navbar'><b>My Social PRO</b><div>
{% if session.get('user_id') %}
<a href='/home' style='color:white;margin:5px'>Home</a>
<a href='/reels' style='color:white;margin:5px'>🎬Reels</a>
<a href='/messenger' style='color:white;margin:5px'>Chat</a>
{% if session.get('is_admin') %}<a href='/admin' style='color:yellow;margin:5px'><b>ADMIN</b></a>{% endif %}
<a href='/logout' style='color:white;margin:5px'>Logout</a>
{% endif %}
</div></div>
{{ content | safe }}
{% if session.get('user_id') %}
<a href='/messenger' class='floating-msg' title='Messenger'>💬</a>
{% endif %}
</body></html>
"""

@app.route("/", methods=["GET","POST"])
def index():
    if request.method=="POST":
        email=request.form['email']; password=request.form['password']
        db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
        q = "SELECT * FROM users WHERE email=%s AND password=%s" if is_pg else "SELECT * FROM users WHERE email=? AND password=?"
        cur.execute(q,(email,password)); user=cur.fetchone(); cur.close(); db.close()
        if user:
            is_blocked = user[4] if is_pg else user['is_blocked']
            uid = user[0] if is_pg else user['id']
            name = user[1] if is_pg else user['name']
            email_db = user[2] if is_pg else user['email']
            if is_blocked == 1:
                return render_template_string(BASE_HTML.replace("{{ content | safe }}","<div class='card'><p style='color:red'>তোমার একাউন্ট Block!</p><a href='/'>Back</a></div>"))
            session["user_id"]=uid; session["name"]=name; session["is_admin"] = True if email_db == ADMIN_EMAIL else False
            return redirect("/home")
        return render_template_string(BASE_HTML.replace("{{ content | safe }}","<div class='card'><p style='color:red'>ভুল ইমেইল/পাসওয়ার্ড</p><a href='/'>আবার চেষ্টা</a></div>"))
    return render_template_string(BASE_HTML.replace("{{ content | safe }}","<div class='card'><h2>Login</h2><form method='post'><input name='email' placeholder='Email' required><input name='password' type='password' placeholder='Password' required><button>Login</button></form><p><a href='/signup'>Create new account</a></p></div>"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method=="POST":
        name=request.form['name']; email=request.form['email'].strip().lower(); password=request.form['password']
        if not re.match(r"^[a-zA-Z0-9._%+-]+@gmail\.com$", email):
            return render_template_string(BASE_HTML.replace("{{ content | safe }}", f"<div class='card'><p style='color:red'>ভাই ফেক Email হবে না! আসল Gmail দাও</p><a href='/signup'>আবার চেষ্টা করো</a></div>"))
        if len(password) < 4:
            return render_template_string(BASE_HTML.replace("{{ content | safe }}","<div class='card'><p style='color:red'>Password কমপক্ষে 4 অক্ষরের হতে হবে!</p><a href='/signup'>Back</a></div>"))
        db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
        try:
            q = "INSERT INTO users (name,email,password,last_seen) VALUES (%s,%s,%s,%s)" if is_pg else "INSERT INTO users (name,email,password,last_seen) VALUES (?,?,?,?)"
            cur.execute(q,(name,email,password,datetime.now().strftime("%Y-%m-%d %H:%M:%S"))); db.commit(); cur.close(); db.close()
            return redirect("/")
        except:
            cur.close(); db.close()
            return render_template_string(BASE_HTML.replace("{{ content | safe }}","<div class='card'><p style='color:red'>এই Email দিয়ে একাউন্ট আগেই খোলা আছে!</p><a href='/signup'>Try again</a></div>"))
    return render_template_string(BASE_HTML.replace("{{ content | safe }}","<div class='card'><h2>Signup - আসল Gmail দিয়ে খুলুন</h2><form method='post'><input name='name' placeholder='Full Name' required><input name='email' placeholder='আসল Gmail যেমন - rahim@gmail.com' required><input name='password' type='password' placeholder='Password (4+ অক্ষর)' required><button>Signup</button></form></div>"))

@app.route("/home", methods=["GET","POST"])
def home():
    if "user_id" not in session: return redirect("/")
    db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
    if request.method=="POST":
        text=request.form.get('text',''); file=request.files.get('file'); filename=None; mtype=None
        if file and file.filename and allowed_file(file.filename):
            if IS_CLOUDINARY and os.environ.get("CLOUDINARY_CLOUD_NAME"):
                upload_result = cloudinary.uploader.upload(file, resource_type="auto")
                filename = upload_result['secure_url']; mtype='video' if upload_result['resource_type']=='video' else 'image'
            else:
                filename=secure_filename(datetime.now().strftime("%Y%m%d%H%M%S_")+file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                mtype='video' if filename.rsplit('.',1)[1].lower() in ['mp4','mov','avi','mkv','webm'] else 'image'
        q = "INSERT INTO posts (user_id,text,media,media_type,time) VALUES (%s,%s,%s,%s,%s)" if is_pg else "INSERT INTO posts (user_id,text,media,media_type,time) VALUES (?,?,?,?,?)"
        cur.execute(q,(session["user_id"],text,filename,mtype,datetime.now().strftime("%Y-%m-%d %H:%M"))); db.commit()
        cur.close(); db.close(); return redirect("/home")
    cur.execute("SELECT posts.*, users.name, users.last_seen FROM posts JOIN users ON posts.user_id=users.id ORDER BY posts.id DESC")
    posts = cur.fetchall()
    html=f"""<div class='card'><h3>Create Post</h3><form method='post' enctype='multipart/form-data'><textarea name='text' placeholder="What's on your mind?"></textarea><input type='file' name='file' accept='image/*,video/*'><button>Post</button></form></div>"""
    for p in posts:
        pid = p[0] if is_pg else p['id']; ptext = p[2] if is_pg else p['text']; pmedia = p[3] if is_pg else p['media']; pmtype = p[4] if is_pg else p['media_type']; pname = p[6] if is_pg else p['name']; plast = p[7] if is_pg else None
        cur.execute("SELECT COUNT(*) FROM likes WHERE post_id=%s" if is_pg else "SELECT COUNT(*) FROM likes WHERE post_id=?", (pid,)); like_count = cur.fetchone()[0]
        cur.execute("SELECT * FROM likes WHERE post_id=%s AND user_id=%s" if is_pg else "SELECT * FROM likes WHERE post_id=? AND user_id=?", (pid, session['user_id'])); liked = cur.fetchone()
        like_text = f"Unlike ({like_count})" if liked else f"Like ({like_count})"
        cur.execute("SELECT comments.*, users.name FROM comments JOIN users ON comments.user_id=users.id WHERE post_id=%s ORDER BY comments.id ASC" if is_pg else "SELECT comments.*, users.name FROM comments JOIN users ON comments.user_id=users.id WHERE post_id=? ORDER BY comments.id ASC", (pid,)); comments = cur.fetchall()
        cmt_html="".join([f"<p style='background:#f0f2f5;padding:5px;border-radius:10px;margin:3px'><b>{c[5] if is_pg else c['name']}:</b> {c[3] if is_pg else c['text']}</p>" for c in comments])
        media_html="";
        if pmedia:
            src = pmedia if pmedia.startswith("http") else f"/static/uploads/{pmedia}"
            if pmtype=='video': media_html=f"<video controls><source src='{src}'></video>"
            else: media_html=f"<img src='{src}'>"
        online_dot = "<span class='dot online'></span>" if is_online(plast) else "<span class='dot offline'></span>"
        html+=f"""<div class='card'><h3>{online_dot} {pname}</h3><p>{ptext}</p>{media_html}<div class='action-bar'><a href='/like/{pid}'><b>{like_text}</b></a><a>Comment ({len(comments)})</a><a href='/share/{pid}'><b>Share</b></a></div><hr>{cmt_html}<form method='post' action='/comment/{pid}' style='display:flex;gap:5px'><input name='text' placeholder='Write a comment...' required><button style='width:80px'>Post</button></form></div>"""
    cur.close(); db.close()
    return render_template_string(BASE_HTML.replace("{{ content | safe }}",html))

@app.route("/reels")
def reels():
    if "user_id" not in session: return redirect("/")
    db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
    cur.execute("SELECT posts.*, users.name FROM posts JOIN users ON posts.user_id=users.id WHERE media_type='video' ORDER BY posts.id DESC")
    posts = cur.fetchall(); cur.close(); db.close()
    html="<div class='card'><h2>🎬 Reels - Short Videos</h2></div>"
    for p in posts:
        ptext = p[2] if is_pg else p['text']; pmedia = p[3] if is_pg else p['media']; pname = p[6] if is_pg else p['name']
        if not pmedia: continue
        src = pmedia if pmedia.startswith("http") else f"/static/uploads/{pmedia}"
        html+=f"""<div class='reel-card'><video controls autoplay muted loop><source src='{src}'></video><div style='padding:10px'><b>{pname}</b><p>{ptext}</p></div></div>"""
    if not posts: html+="<div class='card'><p>এখনো কোনো Reels নাই ভাই, Home থেকে ভিডিও Post করো!</p></div>"
    return render_template_string(BASE_HTML.replace("{{ content | safe }}",html))

@app.route("/like/<int:post_id>")
def like(post_id):
    if "user_id" not in session: return redirect("/")
    db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
    cur.execute("SELECT * FROM likes WHERE post_id=%s AND user_id=%s" if is_pg else "SELECT * FROM likes WHERE post_id=? AND user_id=?", (post_id, session['user_id'])); liked = cur.fetchone()
    if liked: cur.execute("DELETE FROM likes WHERE post_id=%s AND user_id=%s" if is_pg else "DELETE FROM likes WHERE post_id=? AND user_id=?", (post_id, session['user_id']))
    else: cur.execute("INSERT INTO likes (post_id, user_id) VALUES (%s,%s)" if is_pg else "INSERT INTO likes (post_id, user_id) VALUES (?,?)", (post_id, session['user_id']))
    db.commit(); cur.close(); db.close(); return redirect("/home")

@app.route("/share/<int:post_id>")
def share(post_id):
    if "user_id" not in session: return redirect("/")
    db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
    cur.execute("SELECT * FROM posts WHERE id=%s" if is_pg else "SELECT * FROM posts WHERE id=?", (post_id,)); post = cur.fetchone()
    if post:
        ptext = post[2] if is_pg else post['text']; pmedia = post[3] if is_pg else post['media']; pmtype = post[4] if is_pg else post['media_type']
        q = "INSERT INTO posts (user_id,text,media,media_type,time) VALUES (%s,%s,%s,%s,%s)" if is_pg else "INSERT INTO posts (user_id,text,media,media_type,time) VALUES (?,?,?,?,?)"
        cur.execute(q,(session["user_id"], f"Shared: {ptext}", pmedia, pmtype, datetime.now().strftime("%Y-%m-%d %H:%M"))); db.commit()
    cur.close(); db.close(); return redirect("/home")

@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):
    if "user_id" not in session: return redirect("/")
    db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
    q = "INSERT INTO comments (post_id, user_id, text, time) VALUES (%s,%s,%s,%s)" if is_pg else "INSERT INTO comments (post_id, user_id, text, time) VALUES (?,?,?,?)"
    cur.execute(q,(post_id, session["user_id"], request.form['text'], datetime.now().strftime("%H:%M"))); db.commit(); cur.close(); db.close(); return redirect("/home")

@app.route("/messenger", methods=["GET","POST"])
def messenger():
    if "user_id" not in session: return redirect("/")
    db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
    cur.execute("SELECT * FROM users WHERE is_blocked=0"); all_users=cur.fetchall(); selected=request.args.get("user"); chat_html=""
    if selected:
        cur.execute("SELECT * FROM users WHERE id=%s" if is_pg else "SELECT * FROM users WHERE id=?",(selected,)); other=cur.fetchone(); other_name = other[1] if is_pg else other['name']
        if request.method=="POST":
            q = "INSERT INTO messages (sender_id, receiver_id, text, time) VALUES (%s,%s,%s,%s)" if is_pg else "INSERT INTO messages (sender_id, receiver_id, text, time) VALUES (?,?,?,?)"
            cur.execute(q,(session["user_id"], selected, request.form['msg'], datetime.now().strftime("%H:%M"))); db.commit()
        q = "SELECT * FROM messages WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s) ORDER BY id ASC" if is_pg else "SELECT * FROM messages WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?) ORDER BY id ASC"
        cur.execute(q,(session["user_id"],selected,selected,session["user_id"])); msgs=cur.fetchall()
        chat_html=f"<div class='card'><h3>Chat with {other_name}</h3><div style='height:350px;overflow-y:auto;border:1px solid #ddd;padding:10px'>"
        for m in msgs:
            sid = m[1] if is_pg else m['sender_id']; mtext = m[3] if is_pg else m['text']
            align="right" if sid==session["user_id"] else "left"; color="#0084ff" if sid==session["user_id"] else "#f0f0f0"; tcolor="white" if sid==session["user_id"] else "black"
            chat_html+=f"<div style='text-align:{align};margin:5px'><span style='background:{color};color:{tcolor};padding:7px 12px;border-radius:15px;display:inline-block'>{mtext}</span></div>"
        chat_html+=f"</div><form method='post' style='display:flex;gap:5px;margin-top:10px;'><input name='msg' placeholder='Type a message' required style='flex:1'><button style='width:70px'>Send</button></form></div>"
    else: chat_html="<div class='card'><p>Select a friend to start chatting</p></div>"
    list_html="<div class='card'><h3>Messenger - All Friends 🟢Online</h3>"
    for u in all_users:
        uid = u[0] if is_pg else u["id"]; uname = u[1] if is_pg else u["name"]; last = u[5] if is_pg else None
        try: last = u["last_seen"] if not is_pg else last
        except: pass
        if uid!=session["user_id"]:
            dot = "🟢" if is_online(last) else "⚫"
            list_html+=f"<p>{dot} <a href='/messenger?user={uid}'><b>{uname}</b> - Chat Now</a></p>"
    list_html+="</div>"; cur.close(); db.close()
    final_html = f"<div class='messenger-box'><div class='left-list'>{list_html}</div><div class='right-chat'>{chat_html}</div></div>"
    return render_template_string(BASE_HTML.replace("{{ content | safe }}",final_html))

@app.route("/admin")
def admin_panel():
    if not session.get('is_admin'): return "তুমি Admin না! <a href='/home'>Home</a>"
    db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
    cur.execute("SELECT * FROM users"); users=cur.fetchall()
    cur.execute("SELECT posts.*, users.name FROM posts JOIN users ON posts.user_id=users.id ORDER BY posts.id DESC"); posts=cur.fetchall()

    u_html="<div class='card'><h2>Admin Panel - ভাই 👑</h2><h3>All Users</h3>"
    for u in users:
        uemail = u[2] if is_pg else u['email']
        if uemail!= ADMIN_EMAIL:
            uid = u[0] if is_pg else u['id']; uname = u[1] if is_pg else u['name']; is_blocked = u[4] if is_pg else u['is_blocked']
            status = "🔴 Blocked" if is_blocked else "🟢 Active"
            btn = f"<a href='/admin/unblock/{uid}'><button class='success' style='width:90px;padding:5px'>Unblock</button></a>" if is_blocked else f"<a href='/admin/block/{uid}'><button class='danger' style='width:90px;padding:5px'>Block</button></a>"
            u_html+=f"<p style='display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;padding:5px 0'><span>{uname} ({uemail}) - {status}</span> {btn}</p>"
    u_html+="</div>"

    u_html+=f"<div class='card'><h2>All Posts ({len(posts)} টা) <a href='/admin/delete_all' onclick=\"return confirm('সব Post Delete করবা ভাই?')\" style='color:red;font-size:14px'>[Delete All]</a></h2></div>"
    if not posts:
        u_html+="<div class='card'><p>এখনো কোনো Post নাই ভাই!</p></div>"

    for p in posts:
        pid = p[0] if is_pg else p['id']
        ptext = p[2] if is_pg else p['text']
        pmedia = p[3] if is_pg else p['media']
        pmtype = p[4] if is_pg else p['media_type']
        pname = p[6] if is_pg else p['name']

        media_html = ""
        if pmedia:
            src = pmedia if pmedia.startswith("http") else f"/static/uploads/{pmedia}"
            if pmtype == 'video':
                media_html = f"<video controls style='width:100%;max-height:300px;border-radius:8px;margin-top:10px'><source src='{src}'></video>"
            else:
                media_html = f"<img src='{src}' style='width:100%;max-height:300px;object-fit:cover;border-radius:8px;margin-top:10px'>"

        u_html+=f"""
        <div class='card' style='border-left:4px solid #1877f2'>
            <div style='display:flex;justify-content:space-between;align-items:center'>
                <b>{pname} (ID: {pid})</b>
                <a href='/admin/delete_post/{pid}' onclick="return confirm('এই Post টা Delete করবা?')"><button class='danger' style='width:100px;padding:6px'>Delete</button></a>
            </div>
            <p>{ptext}</p>
            {media_html}
        </div>
        """

    cur.close(); db.close()
    return render_template_string(BASE_HTML.replace("{{ content | safe }}",u_html))

@app.route("/admin/block/<int:uid>")
def block_user(uid):
    if not session.get('is_admin'): return redirect("/home")
    db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
    cur.execute("UPDATE users SET is_blocked=1 WHERE id=%s" if is_pg else "UPDATE users SET is_blocked=1 WHERE id=?",(uid,)); db.commit(); cur.close(); db.close(); return redirect("/admin")
@app.route("/admin/unblock/<int:uid>")
def unblock_user(uid):
    if not session.get('is_admin'): return redirect("/home")
    db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
    cur.execute("UPDATE users SET is_blocked=0 WHERE id=%s" if is_pg else "UPDATE users SET is_blocked=0 WHERE id=?",(uid,)); db.commit(); cur.close(); db.close(); return redirect("/admin")
@app.route("/admin/delete_post/<int:pid>")
def delete_post(pid):
    if not session.get('is_admin'): return redirect("/home")
    db=get_db(); cur=db.cursor(); is_pg = os.environ.get("DATABASE_URL") is not None
    cur.execute("DELETE FROM posts WHERE id=%s" if is_pg else "DELETE FROM posts WHERE id=?",(pid,)); cur.execute("DELETE FROM comments WHERE post_id=%s" if is_pg else "DELETE FROM comments WHERE post_id=?",(pid,)); cur.execute("DELETE FROM likes WHERE post_id=%s" if is_pg else "DELETE FROM likes WHERE post_id=?",(pid,)); db.commit(); cur.close(); db.close(); return redirect("/admin")
@app.route("/admin/delete_all")
def delete_all_posts():
    if not session.get('is_admin'): return redirect("/home")
    db=get_db(); cur=db.cursor()
    cur.execute("DELETE FROM posts"); cur.execute("DELETE FROM comments"); cur.execute("DELETE FROM likes")
    db.commit(); cur.close(); db.close()
    return redirect("/admin")
@app.route("/logout")
def logout(): session.clear(); return redirect("/")
if __name__=="__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
