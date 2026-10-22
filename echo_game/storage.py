"""SQLite: actual local save, demo store unlock and best scores."""
from pathlib import Path
import sqlite3, json, time, uuid
from contextlib import contextmanager
BASE=Path(__file__).resolve().parents[1]
class Storage:
    def __init__(self,path=None):
        self.path=Path(path or BASE/'save_data'/'echo.sqlite3')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.session() as db:
            db.execute('CREATE TABLE IF NOT EXISTS saves(id INTEGER PRIMARY KEY CHECK(id=1), snapshot TEXT NOT NULL, updated REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY AUTOINCREMENT, level INTEGER NOT NULL, score INTEGER NOT NULL, seconds REAL NOT NULL, detections INTEGER NOT NULL, ending TEXT, created REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS unlocks(name TEXT PRIMARY KEY, value INTEGER NOT NULL)')
            # Persistent account lives, intentionally independent of story saves.
            db.execute('CREATE TABLE IF NOT EXISTS wallet(id INTEGER PRIMARY KEY CHECK(id=1), lives INTEGER NOT NULL CHECK(lives>=0), unlimited INTEGER NOT NULL DEFAULT 0, defeats INTEGER NOT NULL DEFAULT 0)')
            db.execute('INSERT OR IGNORE INTO wallet(id,lives,unlimited,defeats) VALUES(1,3,0,0)')
            db.execute('CREATE TABLE IF NOT EXISTS demo_purchases(receipt TEXT PRIMARY KEY, product TEXT NOT NULL, price_kzt INTEGER NOT NULL, purchased_at REAL NOT NULL)')
    def connect(self):return sqlite3.connect(self.path)
    @contextmanager
    def session(self):
        """Commit/rollback and always release the Windows file handle."""
        db=self.connect()
        try:
            with db:
                yield db
        finally:
            db.close()
    def save(self,snapshot):
        with self.session() as db:db.execute('INSERT INTO saves(id,snapshot,updated) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot,updated=excluded.updated',(json.dumps(snapshot,ensure_ascii=False),time.time()))
    def load(self):
        with self.session() as db: row=db.execute('SELECT snapshot FROM saves WHERE id=1').fetchone()
        return json.loads(row[0]) if row else None
    def clear(self):
        with self.session() as db:db.execute('DELETE FROM saves')
    def record(self,world,ending=''):
        with self.session() as db:db.execute('INSERT INTO results(level,score,seconds,detections,ending,created) VALUES(?,?,?,?,?,?)',(world.level,world.score,world.time,world.stats['detections'],ending,time.time()))
        self.unlock('Первый шаг')
        if world.stats['detections']==0:self.unlock('Тихий призрак')
        if world.level==3:self.unlock('Эвакуация')
        if 'memory' in world.abilities and 'control' in world.abilities:self.unlock('Память Новы')
        if world.stats['voice_success']>=7:self.unlock('Повелитель терминалов')
    def best(self):
        with self.session() as db:
            rows=db.execute('SELECT level,score,ROUND(seconds,1),detections,COALESCE(ending,"") FROM results ORDER BY score DESC LIMIT 10').fetchall()
        return rows
    def unlock(self,key):
        with self.session() as db:db.execute('INSERT INTO unlocks(name,value) VALUES(?,1) ON CONFLICT(name) DO UPDATE SET value=1',(key,))
    def achievements(self):
        with self.session() as db:
            return [r[0] for r in db.execute('SELECT name FROM unlocks WHERE name != ? AND value=1 ORDER BY name',('premium_challenge',)).fetchall()]
    def has_unlock(self,key):
        with self.session() as db:
            row=db.execute('SELECT value FROM unlocks WHERE name=?',(key,)).fetchone()
        return row is not None

    # Classroom-only freemium prototype: no payment credentials, API, or currency transfers.
    DEMO_PRODUCTS = {
        'lives_3': {'name':'ВОССТАНОВЛЕНИЕ 3 ЖИЗНЕЙ', 'price_kzt':490},
        'premium_pass': {'name':'PREMIUM: БЕЗЛИМИТНЫЕ ЖИЗНИ', 'price_kzt':1490},
    }

    def wallet(self):
        with self.session() as db:
            row=db.execute('SELECT lives,unlimited,defeats FROM wallet WHERE id=1').fetchone()
        return {'lives':int(row[0]),'unlimited':bool(row[1]),'defeats':int(row[2])}

    def can_play(self):
        status=self.wallet()
        return status['unlimited'] or status['lives'] > 0

    def record_defeat(self):
        """Exactly one call per true defeat; never deduct lives for retries or menus."""
        with self.session() as db:
            db.execute('UPDATE wallet SET lives=CASE WHEN unlimited=1 THEN lives WHEN lives>0 THEN lives-1 ELSE 0 END, defeats=defeats+1 WHERE id=1')
            row=db.execute('SELECT lives,unlimited,defeats FROM wallet WHERE id=1').fetchone()
        return {'lives':int(row[0]), 'unlimited':bool(row[1]), 'defeats':int(row[2])}

    def purchase_demo(self,product):
        """Simulate a purchase, generating a local receipt. NEVER collect card data."""
        if product not in self.DEMO_PRODUCTS:raise ValueError('Unknown demo product')
        offer=self.DEMO_PRODUCTS[product]
        receipt='ECHO-DEMO-'+uuid.uuid4().hex[:12].upper()
        with self.session() as db:
            if product=='lives_3':
                db.execute('UPDATE wallet SET lives=lives+3 WHERE id=1')
            else:
                db.execute('UPDATE wallet SET unlimited=1 WHERE id=1')
                db.execute("INSERT INTO unlocks(name,value) VALUES('premium_challenge',1) ON CONFLICT(name) DO UPDATE SET value=1")
            db.execute('INSERT INTO demo_purchases(receipt,product,price_kzt,purchased_at) VALUES(?,?,?,?)',(receipt,product,offer['price_kzt'],time.time()))
        return {'receipt':receipt,'product':product,'name':offer['name'],'price_kzt':offer['price_kzt']}

    def demo_purchases(self):
        with self.session() as db:
            return db.execute('SELECT receipt,product,price_kzt FROM demo_purchases ORDER BY purchased_at DESC').fetchall()
