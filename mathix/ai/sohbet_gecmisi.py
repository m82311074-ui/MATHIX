"""Öğrenci bazında kalıcı AI sohbet geçmişi."""

import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path(__file__).resolve().parent / "sohbet_kayitlari"

def _path(student_id):
    value = str(student_id)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Geçersiz öğrenci kimliği")
    return HISTORY_DIR / f"ogrenci_{value}.json"

def load_chats(student_id):
    try:
        with _path(student_id).open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict) and row.get("id")]
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError, ValueError):
        logging.exception("AI sohbet geçmişi okunamadı")
    return []

def get_chat(student_id, chat_id):
    return next((row for row in load_chats(student_id) if row.get("id") == chat_id), None)

def save_chat(student_id, chat_id, messages):
    """Sohbeti ekle/güncelle; önceki oluşturulma zamanını koru."""
    path = _path(student_id)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    chats = load_chats(student_id)
    old = next((row for row in chats if row.get("id") == chat_id), None)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    clean_messages = [
        {"role": str(m.get("role", "")), "content": str(m.get("content", ""))}
        for m in messages if isinstance(m, dict) and m.get("role") in {"user", "assistant"}
    ]
    first_user = next((m["content"].strip() for m in clean_messages
                       if m["role"] == "user" and m["content"].strip()), "Yeni sohbet")
    row = {
        "id": chat_id, "title": first_user[:64],
        "created_at": old.get("created_at", now) if old else now,
        "updated_at": now, "messages": clean_messages,
    }
    chats = [item for item in chats if item.get("id") != chat_id]
    chats.insert(0, row)
    _write(path, chats)
    return True

def delete_chat(student_id, chat_id):
    chats = load_chats(student_id)
    remaining = [row for row in chats if row.get("id") != chat_id]
    if len(remaining) == len(chats):
        return False
    _write(_path(student_id), remaining)
    return True

def clear_chats(student_id):
    path = _path(student_id)
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        logging.exception("AI sohbet geçmişi temizlenemedi")
        return False

def _write(path, data):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=HISTORY_DIR,
                                         prefix=f".{path.name}.", suffix=".tmp",
                                         delete=False) as f:
            temp_path = Path(f.name)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except OSError:
        logging.exception("AI sohbet geçmişi yazılamadı: %s", path)
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
