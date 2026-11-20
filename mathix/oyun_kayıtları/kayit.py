"""Her öğrenci için ayrı JSON oyun kayıtları."""

import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

KAYIT_DIZINI = Path(__file__).resolve().parent

def oyun_kaydi_ekle(ogrenci, oyun, puan, sonuc, ayrintilar=None):
    """Oturum sonucunu öğrenci kimliğine ait JSON dosyasına ekle."""
    if not isinstance(ogrenci, dict) or ogrenci.get("id") is None:
        return False
    ogrenci_id = str(ogrenci["id"])
    if not re.fullmatch(r"[A-Za-z0-9_-]+", ogrenci_id):
        return False

    dosya = KAYIT_DIZINI / f"ogrenci_{ogrenci_id}.json"
    try:
        KAYIT_DIZINI.mkdir(parents=True, exist_ok=True)
        with dosya.open("r", encoding="utf-8") as f:
            belge = json.load(f)
        if not isinstance(belge, dict) or not isinstance(belge.get("oyunlar"), list):
            belge = {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        belge = {}

    belge.setdefault("ogrenci_id", ogrenci_id)
    belge.setdefault("ogrenci_adi", str(ogrenci.get("ad", ogrenci.get("isim", ""))))
    belge.setdefault("oyunlar", [])
    belge["oyunlar"].append({
        "zaman": datetime.now().astimezone().isoformat(timespec="seconds"),
        "oyun": str(oyun), "puan": int(puan), "sonuc": str(sonuc),
        "ayrintilar": ayrintilar if isinstance(ayrintilar, dict) else {},
    })

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=KAYIT_DIZINI,
                                         prefix=f".{dosya.name}.", suffix=".tmp",
                                         delete=False) as f:
            temp_path = Path(f.name)
            json.dump(belge, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, dosya)
        return True
    except OSError:
        logging.exception("Öğrenci oyun kaydı yazılamadı: %s", dosya)
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False
