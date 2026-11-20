"""Small standard-library clients for optional OpenAI and Gemini chat APIs."""
import json
import threading
import urllib.error
import urllib.request


DEFAULT_MODELS = {
    "ChatGPT": "gpt-4.1-mini",
    "Gemini": "gemini-3.8-flash",
}


def ai_cloud_chat(provider, api_key, model, messages,
                  on_chunk, on_done, on_error, stop_event, on_thinking=None):
    """Run one non-streaming cloud response on a worker thread.

    The key is only passed in memory and is never written to project files.
    """
    def worker():
        try:
            if provider == "ChatGPT":
                payload = {"model": model, "messages": messages, "stream": False}
                request = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Authorization": f"Bearer {api_key}",
                             "Content-Type": "application/json"}, method="POST",
                )
                with urllib.request.urlopen(request, timeout=90) as response:
                    data = json.loads(response.read().decode("utf-8"))
                response_message = data["choices"][0]["message"]
                thought = response_message.get("reasoning_content", "") or ""
                text = response_message.get("content") or ""
            elif provider == "Gemini":
                system = "\n".join(m["content"] for m in messages
                                    if m["role"] == "system")
                contents = []
                for message in messages:
                    if message["role"] == "system":
                        continue
                    contents.append({
                        "role": "model" if message["role"] == "assistant" else "user",
                        "parts": [{"text": message["content"]}],
                    })
                payload = {"contents": contents}
                if system:
                    payload["systemInstruction"] = {"parts": [{"text": system}]}
                request = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"x-goog-api-key": api_key,
                             "Content-Type": "application/json"}, method="POST",
                )
                with urllib.request.urlopen(request, timeout=90) as response:
                    data = json.loads(response.read().decode("utf-8"))
                thought_parts, answer_parts = [], []
                for part in data["candidates"][0]["content"]["parts"]:
                    (thought_parts if part.get("thought") else answer_parts).append(
                        part.get("text", ""))
                thought = "".join(thought_parts)
                text = "".join(answer_parts)
            else:
                raise ValueError("Desteklenmeyen API sağlayıcısı.")

            if stop_event.is_set():
                on_done("", True)
                return
            if thought and on_thinking:
                on_thinking(thought)
            if text:
                on_chunk(text)
            on_done(text, False)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc)
            on_error(f"{exc.code}: {detail[:1200]}")
        except Exception as exc:
            on_error(str(exc))

    threading.Thread(target=worker, daemon=True).start()
