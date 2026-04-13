from io import BytesIO
import math
import wave


def build_test_wav_bytes(
    amplitude: int = 8000,
    sample_rate: int = 8000,
    duration_seconds: float = 0.25,
) -> bytes:
    frame_count = int(sample_rate * duration_seconds)
    buffer = BytesIO()

    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()
        for frame_index in range(frame_count):
            angle = 2 * math.pi * 440 * (frame_index / sample_rate)
            sample = int(amplitude * math.sin(angle))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))

        wav_file.writeframes(bytes(frames))

    return buffer.getvalue()


def test_audio_ingestion_accepts_valid_upload(client) -> None:
    wav_payload = build_test_wav_bytes()

    response = client.post(
        "/api/v1/audio/ingestions",
        data={
            "device_key": "Living Room Phone",
            "captured_at": "2026-04-13T09:45:00Z",
        },
        files={"audio_file": ("sample.wav", wav_payload, "audio/wav")},
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "accepted"
    assert payload["device_key"] == "Living Room Phone"
    assert payload["content_type"] == "audio/wav"
    assert payload["size_bytes"] > 0
    assert payload["sample"]["duration_seconds"] > 0
    assert payload["sample"]["sample_rate_hz"] == 8000
    assert payload["sample"]["channel_count"] == 1
    assert payload["sample"]["normalized_rms"] > 0
    assert payload["sample"]["normalized_peak"] > 0
    assert payload["alerts"] == []
    assert payload["notifications"] == []


def test_audio_ingestion_rejects_unsupported_type(client) -> None:
    response = client.post(
        "/api/v1/audio/ingestions",
        data={"device_key": "living-room-phone"},
        files={"audio_file": ("sample.mp3", b"not-audio", "audio/mpeg")},
    )

    assert response.status_code == 415
    assert "Unsupported audio type" in response.json()["detail"]


def test_audio_ingestion_rejects_empty_files(client) -> None:
    response = client.post(
        "/api/v1/audio/ingestions",
        data={"device_key": "living-room-phone"},
        files={"audio_file": ("empty.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Audio upload is empty."


def test_audio_ingestion_rejects_invalid_wav_payload(client) -> None:
    response = client.post(
        "/api/v1/audio/ingestions",
        data={"device_key": "living-room-phone"},
        files={"audio_file": ("broken.wav", b"not-a-real-wav", "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid WAV payload. Use standard PCM WAV audio."


def test_audio_ingestion_creates_spike_alert(client) -> None:
    wav_payload = build_test_wav_bytes(amplitude=30000)

    response = client.post(
        "/api/v1/audio/ingestions",
        data={"device_key": "living-room-phone"},
        files={"audio_file": ("spike.wav", wav_payload, "audio/wav")},
    )

    payload = response.json()

    assert response.status_code == 200
    assert any(alert["type"] == "spike_peak" for alert in payload["alerts"])
    assert payload["notifications"][0]["status"] == "skipped"
    assert payload["notifications"][0]["channel"] == "telegram"


def test_audio_ingestion_creates_sustained_noise_alert(client) -> None:
    wav_payload = build_test_wav_bytes(amplitude=10000)
    last_payload = None

    for _ in range(4):
        response = client.post(
            "/api/v1/audio/ingestions",
            data={"device_key": "living-room-phone"},
            files={"audio_file": ("steady.wav", wav_payload, "audio/wav")},
        )
        last_payload = response.json()

    assert response.status_code == 200
    assert last_payload is not None
    assert any(alert["type"] == "sustained_noise" for alert in last_payload["alerts"])


def test_audio_ingestion_creates_repeated_peaks_alert(client) -> None:
    wav_payload = build_test_wav_bytes(amplitude=20000)
    last_payload = None

    for _ in range(3):
        response = client.post(
            "/api/v1/audio/ingestions",
            data={"device_key": "living-room-phone"},
            files={"audio_file": ("repeat.wav", wav_payload, "audio/wav")},
        )
        last_payload = response.json()

    assert response.status_code == 200
    assert last_payload is not None
    assert any(alert["type"] == "repeated_peaks" for alert in last_payload["alerts"])


def test_audio_ingestion_records_successful_telegram_delivery(client, monkeypatch) -> None:
    from app.services import notification_delivery

    class FakeSettings:
        telegram_bot_token = "bot-token"
        telegram_chat_id = "123456"
        telegram_api_base_url = "https://example.invalid"
        notification_request_timeout_seconds = 10

    def fake_send_telegram_message(text: str) -> tuple[int, dict]:
        assert "SoundSentinel alert" in text
        return 200, {"result": {"message_id": 42}}

    monkeypatch.setattr(notification_delivery, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(notification_delivery, "_send_telegram_message", fake_send_telegram_message)

    wav_payload = build_test_wav_bytes(amplitude=30000)
    response = client.post(
        "/api/v1/audio/ingestions",
        data={"device_key": "living-room-phone"},
        files={"audio_file": ("notify.wav", wav_payload, "audio/wav")},
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["notifications"][0]["status"] == "sent"
    assert payload["notifications"][0]["recipient"] == "123456"
