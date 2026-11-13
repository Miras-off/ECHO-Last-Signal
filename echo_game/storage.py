"""SQLite: actual local save, demo store unlock and best scores."""
from pathlib import Path
import sqlite3, json, time, uuid, math
from contextlib import contextmanager
BASE=Path(__file__).resolve().parents[1]
class Storage:
    # Free-to-play regeneration: a single life every 15 minutes, at most 3 free lives.
    # Paid attempts above this limit are kept; they do not get a free timer.
    MAX_FREE_LIVES = 3
    LIFE_REGEN_SECONDS = 15 * 60

    def __init__(self,path=None,clock=None):
        self._clock = clock if clock is not None else time.time
        self.path=Path(path or BASE/'save_data'/'echo.sqlite3')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.session() as db:
            db.execute('CREATE TABLE IF NOT EXISTS saves(id INTEGER PRIMARY KEY CHECK(id=1), snapshot TEXT NOT NULL, updated REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY AUTOINCREMENT, level INTEGER NOT NULL, score INTEGER NOT NULL, seconds REAL NOT NULL, detections INTEGER NOT NULL, ending TEXT, created REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS unlocks(name TEXT PRIMARY KEY, value INTEGER NOT NULL)')
            # Persistent account lives, intentionally independent of story saves.
            db.execute('CREATE TABLE IF NOT EXISTS wallet(id INTEGER PRIMARY KEY CHECK(id=1), lives INTEGER NOT NULL CHECK(lives>=0), unlimited INTEGER NOT NULL DEFAULT 0, defeats INTEGER NOT NULL DEFAULT 0)')
            # Migrate an existing v2.1.2 database in place; keep lives and purchases.
            columns={row[1] for row in db.execute('PRAGMA table_info(wallet)')}
            if 'regen_started_at' not in columns:
                db.execute('ALTER TABLE wallet ADD COLUMN regen_started_at REAL')
            db.execute('INSERT OR IGNORE INTO wallet(id,lives,unlimited,defeats) VALUES(1,3,0,0)')
            self._refresh_lives(db,self._clock())
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

    def _refresh_lives(self,db,now):
        """Settle elapsed offline time in the same SQLite transaction.

        A free timer starts on the first loss below the 3-life free cap.
        Reading the wallet cannot award multiple lives for the same 15 minutes.
        """
        lives,unlimited,defeats,started=db.execute(
            'SELECT lives,unlimited,defeats,regen_started_at FROM wallet WHERE id=1'
        ).fetchone()
        lives=int(lives)
        unlimited=bool(unlimited)
        now=float(now)
        if unlimited or lives>=self.MAX_FREE_LIVES:
            if started is not None:
                db.execute('UPDATE wallet SET regen_started_at=NULL WHERE id=1')
            started=None
        elif started is None or float(started)>now:
            # An old save starts regenerating from its first v2.1.3 launch.
            # Also recover safely if the computer clock was adjusted backward.
            started=now
            db.execute('UPDATE wallet SET regen_started_at=? WHERE id=1',(started,))
        else:
            periods=int((now-float(started))//self.LIFE_REGEN_SECONDS)
            gained=min(self.MAX_FREE_LIVES-lives,max(0,periods))
            if gained:
                lives+=gained
                started=None if lives>=self.MAX_FREE_LIVES else float(started)+gained*self.LIFE_REGEN_SECONDS
                db.execute('UPDATE wallet SET lives=?,regen_started_at=? WHERE id=1',(lives,started))
        return {'lives':lives,'unlimited':unlimited,'defeats':int(defeats),'regen_started_at':started}

    def recovery_status(self):
        """Current wallet with persistent remaining cooldown, refreshed on every read."""
        with self.session() as db:
            status=self._refresh_lives(db,self._clock())
            now=self._clock()
        started=status.pop('regen_started_at')
        if started is None or status['unlimited'] or status['lives']>=self.MAX_FREE_LIVES:
            remaining=None
        else:
            remaining=max(0,math.ceil(self.LIFE_REGEN_SECONDS-(now-float(started))))
        return {**status,'next_life_in':remaining,'max_free_lives':self.MAX_FREE_LIVES,
                'regen_interval_seconds':self.LIFE_REGEN_SECONDS}

    def wallet(self):
        status=self.recovery_status()
        return {key:status[key] for key in ('lives','unlimited','defeats')}

    def can_play(self):
        status=self.wallet()
        return status['unlimited'] or status['lives'] > 0

    def record_defeat(self):
        """Deduct one life per real defeat; regeneration is clock-based, not FPS-based."""
        with self.session() as db:
            now=self._clock()
            status=self._refresh_lives(db,now)
            if not status['unlimited'] and status['lives']>0:
                new_lives=status['lives']-1
                # Keep a running countdown if already recovering; start it on
                # the first loss from a full (or purchased >3) wallet.
                started=status['regen_started_at']
                if new_lives<self.MAX_FREE_LIVES and started is None:
                    started=now
                db.execute('UPDATE wallet SET lives=?, defeats=defeats+1, regen_started_at=? WHERE id=1',
                           (new_lives,started))
            else:
                db.execute('UPDATE wallet SET defeats=defeats+1 WHERE id=1')
            row=db.execute('SELECT lives,unlimited,defeats FROM wallet WHERE id=1').fetchone()
        return {'lives':int(row[0]),'unlimited':bool(row[1]),'defeats':int(row[2])}

    def purchase_demo(self,product):
        """Simulate a purchase, generating a local receipt. NEVER collect card data."""
        if product not in self.DEMO_PRODUCTS:raise ValueError('Unknown demo product')
        offer=self.DEMO_PRODUCTS[product]
        receipt='ECHO-DEMO-'+uuid.uuid4().hex[:12].upper()
        with self.session() as db:
            self._refresh_lives(db,self._clock())
            if product=='lives_3':
                db.execute('UPDATE wallet SET lives=lives+3, regen_started_at=NULL WHERE id=1')
            else:
                db.execute('UPDATE wallet SET unlimited=1, regen_started_at=NULL WHERE id=1')
                db.execute("INSERT INTO unlocks(name,value) VALUES('premium_challenge',1) ON CONFLICT(name) DO UPDATE SET value=1")
            db.execute('INSERT INTO demo_purchases(receipt,product,price_kzt,purchased_at) VALUES(?,?,?,?)',(receipt,product,offer['price_kzt'],self._clock()))
        return {'receipt':receipt,'product':product,'name':offer['name'],'price_kzt':offer['price_kzt']}

    def demo_purchases(self):
        with self.session() as db:
            return db.execute('SELECT receipt,product,price_kzt FROM demo_purchases ORDER BY purchased_at DESC').fetchall()
