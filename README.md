# 🤖 MATHİX — Ollama Kurulumu

MATHİX'in yapay zekâ özelliklerini kullanabilmek için sisteminizde **Ollama** ve en az bir yapay zekâ modeli kurulu olmalıdır.

## 🧠 MATHİX'te Kullanılabilecek Modeller

| Model            |               Boyut | Yaklaşık indirme boyutu | Özellik                                 |
| ---------------- | ------------------: | ----------------------: | --------------------------------------- |
| **Gemma 3 4B**   |  4 milyar parametre |                 ~3.3 GB | Hızlı, görüntü destekli                 |
| **Gemma 3 12B**  | 12 milyar parametre |                 ~8.1 GB | Daha güçlü, görüntü destekli            |
| **Gemma 3 27B**  | 27 milyar parametre |                  ~17 GB | Çok daha güçlü, daha fazla kaynak ister |
| **Llama 3 8B**   |  8 milyar parametre |                 ~4.7 GB | Güçlü genel amaçlı model                |
| **Llama 3.2 3B** |  3 milyar parametre |                 ~2.0 GB | Hafif ve hızlı                          |
| **Llama 3.2 1B** |  1 milyar parametre |                 ~1.3 GB | Çok hafif sistemler için                |

Boyutlar kullanılan quantization sürümüne göre değişebilir. Ollama'nın güncel model sayfalarında Gemma 3 ve Llama modellerinin farklı boyutları listelenmektedir.

### ⚡ Hızlı ve hafif

```bash
ollama pull llama3.2:3b
```

### 🧠 Daha güçlü

```bash
ollama pull llama3:8b
```

### 👁️ Görsel destekli Gemma

```bash
ollama pull gemma3:4b
```

Gemma 3'ün 4B, 12B ve 27B sürümleri görüntü girdisini destekler ve 128K bağlam penceresine sahiptir.

---

## 🪟 Windows

### 1. Ollama'yı indir

Resmî Ollama sitesinden Windows sürümünü indirin ve kurulum dosyasını çalıştırın.

### 2. Kurulumu kontrol et

PowerShell veya Komut İstemi'ni açın:

```powershell
ollama --version
```

### 3. Bir model indirin

Örneğin:

```powershell
ollama pull gemma3:4b
```

### 4. Test edin

```powershell
ollama run gemma3:4b
```

---

## 🍎 macOS

Ollama uygulamasını kurduktan sonra Terminal'i açın:

```bash
ollama --version
```

Modeli indirin:

```bash
ollama pull gemma3:4b
```

Test edin:

```bash
ollama run gemma3:4b
```

---

# 🐧 Debian / Ubuntu

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

```bash
ollama --version
```

```bash
sudo systemctl enable --now ollama
```

Model:

```bash
ollama pull gemma3:4b
```

Test:

```bash
ollama run gemma3:4b
```

---

# 🏹 Arch Linux / CachyOS

```bash
sudo pacman -S ollama
```

```bash
sudo systemctl enable --now ollama
```

Kontrol:

```bash
ollama --version
```

Model:

```bash
ollama pull gemma3:4b
```

Test:

```bash
ollama run gemma3:4b
```

> CachyOS, Arch Linux tabanlı olduğu için bu yöntem kullanılabilir.

---

# 🎩 Fedora

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

```bash
sudo systemctl enable --now ollama
```

```bash
ollama --version
```

Model:

```bash
ollama pull gemma3:4b
```

Test:

```bash
ollama run gemma3:4b
```

---

# 🧪 MATHİX bağlantısını test etme

Ollama çalışıyorsa MATHİX varsayılan olarak:

```text
http://localhost:11434
```

adresindeki API'yi kullanabilir.

Python tarafında ekstra Ollama paketi zorunlu değildir. MATHİX'in mevcut `urllib.request` modülüyle doğrudan API'ye bağlanılabilir.

```python
import json
import urllib.request

data = {
    "model": "gemma3:4b",
    "prompt": "Merhaba MATHİX!",
    "stream": False
}

request = urllib.request.Request(
    "http://localhost:11434/api/generate",
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(request) as response:
    result = json.loads(response.read().decode("utf-8"))

print(result["response"])
```

## 💡 Başlangıç önerisi

MATHİX için hafif başlangıç modeli:

```bash
ollama pull gemma3:4b
```

Daha düşük sistem kaynakları için:

```bash
ollama pull llama3.2:3b
```

Daha güçlü sistemlerde:

```bash
ollama pull gemma3:12b
```

veya:

```bash
ollama pull llama3:8b
```
