"""SQLite: actual local save, demo store unlock and best scores."""
from pathlib import Path
import sqlite3, json, time
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
