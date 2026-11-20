"""MATHİX — SQLite veri kaydı ve istatistik sorguları."""
import sqlite3
import hashlib
import hmac
import secrets
from datetime import datetime
from pathlib import Path

# Veritabanı dosyası: proje kökünde "mathix_data.db"
DB_PATH = Path(__file__).resolve().parent.parent / "mathix_data.db"


def _conn():
    """Bağlantı aç (her çağrıda taze)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Tabloları oluştur. Idempotent — birden fazla çağrılabilir."""
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS ogrenci (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isim TEXT NOT NULL,
            sinif INTEGER NOT NULL,
            sifre_hash TEXT,
            olusturma TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS oturum (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER,
            mod TEXT NOT NULL,
            sinif INTEGER NOT NULL,
            zorluk TEXT NOT NULL,
            baslangic TEXT NOT NULL,
            bitis TEXT,
            toplam_puan INTEGER DEFAULT 0,
            dogru INTEGER DEFAULT 0,
            yanlis INTEGER DEFAULT 0,
            FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id)
        );

        CREATE TABLE IF NOT EXISTS cevap (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oturum_id INTEGER NOT NULL,
            soru_no INTEGER,
            soru_metni TEXT NOT NULL,
            verilen_cevap TEXT,
            dogru_cevap TEXT,
            dogru_mu INTEGER NOT NULL,
            sure_sn REAL,
            kaynak TEXT,
            zaman TEXT NOT NULL,
            FOREIGN KEY(oturum_id) REFERENCES oturum(id)
        );

        CREATE INDEX IF NOT EXISTS idx_cevap_oturum ON cevap(oturum_id);
        CREATE INDEX IF NOT EXISTS idx_oturum_ogrenci ON oturum(ogrenci_id);

        CREATE TABLE IF NOT EXISTS koruma_olayi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oyun TEXT NOT NULL,
            uygulama TEXT NOT NULL,
            zaman TEXT NOT NULL,
            ogrenci_id INTEGER,
            FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id)
        );
        CREATE INDEX IF NOT EXISTS idx_koruma_zaman ON koruma_olayi(zaman);
        """)
        # Add student association to databases created by older versions.
        columns = {row[1] for row in c.execute("PRAGMA table_info(koruma_olayi)")}
        if "ogrenci_id" not in columns:
            c.execute("ALTER TABLE koruma_olayi ADD COLUMN ogrenci_id INTEGER")
        student_columns = {row[1] for row in c.execute("PRAGMA table_info(ogrenci)")}
        if "sifre_hash" not in student_columns:
            c.execute("ALTER TABLE ogrenci ADD COLUMN sifre_hash TEXT")


# ---------------- Kayıt fonksiyonları ----------------

def _sifre_hashle(sifre, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"),
                                 bytes.fromhex(salt), 310_000).hex()
    return f"pbkdf2_sha256$310000${salt}${digest}"


def ogrenci_ekle(isim, sinif, sifre=None):
    password_hash = _sifre_hashle(sifre) if sifre else None
    with _conn() as c:
        if c.execute("SELECT 1 FROM ogrenci WHERE isim=? COLLATE NOCASE",
                     (isim.strip(),)).fetchone():
            raise ValueError("Bu giriş adı başka bir öğrenci tarafından kullanılıyor.")
        cur = c.execute(
            "INSERT INTO ogrenci(isim, sinif, sifre_hash, olusturma) VALUES (?,?,?,?)",
            (isim.strip(), int(sinif), password_hash,
             datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def ogrenci_hesabi_guncelle(ogrenci_id, isim, sinif, sifre=None):
    """Update an account; an empty password preserves the existing password."""
    with _conn() as c:
        duplicate = c.execute(
            "SELECT id FROM ogrenci WHERE isim=? COLLATE NOCASE AND id<>?",
            (isim.strip(), ogrenci_id),
        ).fetchone()
        if duplicate:
            raise ValueError("Bu giriş adı başka bir öğrenci tarafından kullanılıyor.")
        if sifre:
            c.execute(
                "UPDATE ogrenci SET isim=?, sinif=?, sifre_hash=? WHERE id=?",
                (isim.strip(), int(sinif), _sifre_hashle(sifre), ogrenci_id),
            )
        else:
            c.execute(
                "UPDATE ogrenci SET isim=?, sinif=? WHERE id=?",
                (isim.strip(), int(sinif), ogrenci_id),
            )


def ogrenci_giris(isim, sifre):
    """Return account details after constant-time password verification."""
    with _conn() as c:
        row = c.execute(
            "SELECT id, isim, sinif, sifre_hash FROM ogrenci "
            "WHERE isim=? COLLATE NOCASE LIMIT 1", (isim.strip(),),
        ).fetchone()
    if not row or not row["sifre_hash"]:
        return None
    try:
        algorithm, rounds, salt, expected = row["sifre_hash"].split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return None
        actual = hashlib.pbkdf2_hmac(
            "sha256", sifre.encode("utf-8"), bytes.fromhex(salt), int(rounds)
        ).hex()
        if not hmac.compare_digest(actual, expected):
            return None
    except (ValueError, TypeError):
        return None
    return {"id": row["id"], "isim": row["isim"], "sinif": row["sinif"]}


def ogrenci_bul_veya_ekle(isim, sinif):
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM ogrenci WHERE isim=? AND sinif=? ORDER BY id DESC LIMIT 1",
            (isim, sinif),
        ).fetchone()
        if row:
            return row["id"]
    return ogrenci_ekle(isim, sinif)


def oturum_baslat(ogrenci_id, mod, sinif, zorluk):
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO oturum(ogrenci_id, mod, sinif, zorluk, baslangic)
               VALUES (?,?,?,?,?)""",
            (ogrenci_id, mod, sinif, zorluk,
             datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def oturum_bitir(oturum_id, puan, dogru, yanlis):
    with _conn() as c:
        c.execute(
            """UPDATE oturum SET bitis=?, toplam_puan=?, dogru=?, yanlis=?
               WHERE id=?""",
            (datetime.now().isoformat(timespec="seconds"),
             puan, dogru, yanlis, oturum_id),
        )


def cevap_kaydet(oturum_id, soru_no, soru_metni, verilen, dogru_cevap,
                 dogru_mu, sure_sn, kaynak):
    with _conn() as c:
        c.execute(
            """INSERT INTO cevap(oturum_id, soru_no, soru_metni, verilen_cevap,
                                 dogru_cevap, dogru_mu, sure_sn, kaynak, zaman)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (oturum_id, soru_no, soru_metni, str(verilen), str(dogru_cevap),
             1 if dogru_mu else 0, sure_sn, kaynak,
             datetime.now().isoformat(timespec="seconds")),
        )


def koruma_olayi_kaydet(oyun, uygulama, ogrenci_id=None):
    with _conn() as c:
        c.execute(
            "INSERT INTO koruma_olayi(oyun, uygulama, zaman, ogrenci_id) VALUES (?,?,?,?)",
            (oyun, uygulama, datetime.now().isoformat(timespec="seconds"), ogrenci_id),
        )


def koruma_kayitlari(limit=500):
    with _conn() as c:
        return [dict(row) for row in c.execute(
            "SELECT k.id, k.oyun, k.uygulama, k.zaman, k.ogrenci_id, "
            "COALESCE(o.isim, 'Belirtilmedi') AS ogrenci_isim "
            "FROM koruma_olayi k LEFT JOIN ogrenci o ON o.id=k.ogrenci_id "
            "ORDER BY k.id DESC LIMIT ?", (limit,),
        ).fetchall()]


def koruma_kayitlarini_temizle():
    with _conn() as c:
        c.execute("DELETE FROM koruma_olayi")


def ogrenci_koruma_kayitlari(ogrenci_id, limit=200):
    with _conn() as c:
        return [dict(row) for row in c.execute(
            "SELECT id, oyun, uygulama, zaman FROM koruma_olayi "
            "WHERE ogrenci_id=? ORDER BY id DESC LIMIT ?", (ogrenci_id, limit),
        ).fetchall()]


# ---------------- İstatistik sorguları ----------------

def genel_istatistik():
    with _conn() as c:
        return dict(c.execute("""
            SELECT
              (SELECT COUNT(*) FROM ogrenci) AS ogrenci_sayisi,
              (SELECT COUNT(*) FROM oturum)  AS oturum_sayisi,
              (SELECT COUNT(*) FROM cevap)   AS cevap_sayisi,
              (SELECT COALESCE(SUM(dogru_mu),0) FROM cevap) AS dogru_sayisi,
              (SELECT COALESCE(AVG(sure_sn),0) FROM cevap
               WHERE sure_sn IS NOT NULL) AS ort_sure
        """).fetchone())


def sinif_bazli_basari():
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT o.sinif,
                   COUNT(c.id) AS toplam,
                   SUM(c.dogru_mu) AS dogru,
                   ROUND(100.0*SUM(c.dogru_mu)/COUNT(c.id), 1) AS basari_yuzde
            FROM cevap c
            JOIN oturum o ON o.id = c.oturum_id
            GROUP BY o.sinif
            ORDER BY o.sinif
        """).fetchall()]


def zorluk_bazli_basari():
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT o.zorluk,
                   COUNT(c.id) AS toplam,
                   ROUND(100.0*SUM(c.dogru_mu)/COUNT(c.id), 1) AS basari_yuzde,
                   ROUND(AVG(c.sure_sn), 2) AS ort_sure
            FROM cevap c
            JOIN oturum o ON o.id = c.oturum_id
            GROUP BY o.zorluk
            ORDER BY o.zorluk
        """).fetchall()]


def mod_bazli_basari():
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT o.mod,
                   COUNT(c.id) AS toplam,
                   ROUND(100.0*SUM(c.dogru_mu)/COUNT(c.id), 1) AS basari_yuzde
            FROM cevap c
            JOIN oturum o ON o.id = c.oturum_id
            GROUP BY o.mod
            ORDER BY basari_yuzde DESC
        """).fetchall()]

# ==============================================================================
# ÖĞRETMEN PANELİ SORGULARI
# ==============================================================================

def tum_ogrenciler():
    """Tüm öğrencileri + özet istatistiklerini listeler."""
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT
                o.id, o.isim, o.sinif, (o.sifre_hash IS NOT NULL) AS hesap_var,
                COUNT(DISTINCT ot.id) AS oturum_sayisi,
                COALESCE(SUM(ot.toplam_puan), 0) AS toplam_puan,
                COALESCE(SUM(ot.dogru), 0) AS dogru,
                COALESCE(SUM(ot.yanlis), 0) AS yanlis,
                MAX(ot.bitis) AS son_oynama
            FROM ogrenci o
            LEFT JOIN oturum ot ON ot.ogrenci_id = o.id
            GROUP BY o.id
            ORDER BY o.sinif, o.isim
        """).fetchall()]


def sinif_ogrencileri(sinif):
    """Belirli bir sınıftaki öğrenciler."""
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT
                o.id, o.isim, o.sinif, (o.sifre_hash IS NOT NULL) AS hesap_var,
                COUNT(DISTINCT ot.id) AS oturum_sayisi,
                COALESCE(SUM(ot.toplam_puan), 0) AS toplam_puan,
                COALESCE(SUM(ot.dogru), 0) AS dogru,
                COALESCE(SUM(ot.yanlis), 0) AS yanlis,
                MAX(ot.bitis) AS son_oynama
            FROM ogrenci o
            LEFT JOIN oturum ot ON ot.ogrenci_id = o.id
            WHERE o.sinif = ?
            GROUP BY o.id
            ORDER BY o.isim
        """, (sinif,)).fetchall()]


def ogrenci_oturumlari(ogrenci_id):
    """Bir öğrencinin tüm oturumları (en yeniden eskiye)."""
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT id, mod, sinif, zorluk, baslangic, bitis,
                   toplam_puan, dogru, yanlis
            FROM oturum
            WHERE ogrenci_id = ?
            ORDER BY id DESC
        """, (ogrenci_id,)).fetchall()]


def ogrenci_cevaplari(ogrenci_id, limit=200):
    """Bir öğrencinin son cevapları."""
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT c.id, c.soru_metni, c.verilen_cevap, c.dogru_cevap,
                   c.dogru_mu, c.sure_sn, c.kaynak, c.zaman,
                   o.mod, o.zorluk
            FROM cevap c
            JOIN oturum o ON o.id = c.oturum_id
            WHERE o.ogrenci_id = ?
            ORDER BY c.id DESC
            LIMIT ?
        """, (ogrenci_id, limit)).fetchall()]


def ogrenci_ozet(ogrenci_id):
    """Bir öğrencinin genel özeti."""
    with _conn() as c:
        row = c.execute("""
            SELECT
                o.isim, o.sinif, (o.sifre_hash IS NOT NULL) AS hesap_var,
                COUNT(DISTINCT ot.id) AS oturum_sayisi,
                COUNT(c.id) AS cevap_sayisi,
                COALESCE(SUM(c.dogru_mu), 0) AS dogru,
                COUNT(c.id) - COALESCE(SUM(c.dogru_mu), 0) AS yanlis,
                ROUND(AVG(c.sure_sn), 2) AS ort_sure,
                COALESCE(SUM(ot.toplam_puan), 0) AS toplam_puan
            FROM ogrenci o
            LEFT JOIN oturum ot ON ot.ogrenci_id = o.id
            LEFT JOIN cevap c ON c.oturum_id = ot.id
            WHERE o.id = ?
            GROUP BY o.id
        """, (ogrenci_id,)).fetchone()
        return dict(row) if row else None


def ogrenci_zorlandigi_sorular(ogrenci_id, limit=15):
    """Öğrencinin en çok yanlış yaptığı sorular."""
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT soru_metni, dogru_cevap, COUNT(*) AS tekrar
            FROM cevap c
            JOIN oturum o ON o.id = c.oturum_id
            WHERE o.ogrenci_id = ? AND c.dogru_mu = 0
            GROUP BY soru_metni
            ORDER BY tekrar DESC
            LIMIT ?
        """, (ogrenci_id, limit)).fetchall()]


def sinif_bazli_basari():
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT o.sinif,
                   COUNT(c.id) AS toplam,
                   SUM(c.dogru_mu) AS dogru,
                   ROUND(100.0*SUM(c.dogru_mu)/COUNT(c.id), 1) AS basari_yuzde
            FROM cevap c
            JOIN oturum o ON o.id = c.oturum_id
            GROUP BY o.sinif
            ORDER BY o.sinif
        """).fetchall()]


def zorluk_bazli_basari():
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT o.zorluk,
                   COUNT(c.id) AS toplam,
                   ROUND(100.0*SUM(c.dogru_mu)/COUNT(c.id), 1) AS basari_yuzde,
                   ROUND(AVG(c.sure_sn), 2) AS ort_sure
            FROM cevap c
            JOIN oturum o ON o.id = c.oturum_id
            GROUP BY o.zorluk
            ORDER BY o.zorluk
        """).fetchall()]


def mod_bazli_basari():
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT o.mod,
                   COUNT(c.id) AS toplam,
                   ROUND(100.0*SUM(c.dogru_mu)/COUNT(c.id), 1) AS basari_yuzde
            FROM cevap c
            JOIN oturum o ON o.id = c.oturum_id
            GROUP BY o.mod
            ORDER BY basari_yuzde DESC
        """).fetchall()]


def genel_istatistik():
    with _conn() as c:
        return dict(c.execute("""
            SELECT
              (SELECT COUNT(*) FROM ogrenci) AS ogrenci_sayisi,
              (SELECT COUNT(*) FROM oturum)  AS oturum_sayisi,
              (SELECT COUNT(*) FROM cevap)   AS cevap_sayisi,
              (SELECT COALESCE(SUM(dogru_mu),0) FROM cevap) AS dogru_sayisi,
              (SELECT COALESCE(AVG(sure_sn),0) FROM cevap
               WHERE sure_sn IS NOT NULL) AS ort_sure
        """).fetchone())

# ==============================================================================
# ÖĞRENCİ YÖNETİMİ (Ekle / Düzenle / Sil)
# ==============================================================================

def ogrenci_guncelle(ogrenci_id, yeni_isim, yeni_sinif):
    """Öğrencinin isim ve sınıfını güncelle."""
    with _conn() as c:
        c.execute(
            "UPDATE ogrenci SET isim=?, sinif=? WHERE id=?",
            (yeni_isim.strip(), int(yeni_sinif), ogrenci_id),
        )


def ogrenci_sil(ogrenci_id):
    """Öğrenciyi ve bağlı TÜM oturum/cevap kayıtlarını sil."""
    with _conn() as c:
        # Önce cevapları sil
        c.execute("""
            DELETE FROM cevap WHERE oturum_id IN (
                SELECT id FROM oturum WHERE ogrenci_id = ?
            )
        """, (ogrenci_id,))
        # Sonra oturumları sil
        c.execute("DELETE FROM oturum WHERE ogrenci_id = ?", (ogrenci_id,))
        # Son olarak öğrenciyi sil
        c.execute("DELETE FROM ogrenci WHERE id = ?", (ogrenci_id,))


def ogrenci_istatistik_topla(ogrenci_id):
    """Silme onayı için öğrencinin kaç kaydı olduğunu say."""
    with _conn() as c:
        row = c.execute("""
            SELECT
                (SELECT COUNT(*) FROM oturum WHERE ogrenci_id = ?) AS oturum,
                (SELECT COUNT(*) FROM cevap WHERE oturum_id IN (
                    SELECT id FROM oturum WHERE ogrenci_id = ?
                )) AS cevap
        """, (ogrenci_id, ogrenci_id)).fetchone()
        return dict(row) if row else {"oturum": 0, "cevap": 0}
