def test_dashboard_shows_empty_state(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "No sensors have reported data yet." in body
    assert "No sound samples available yet." in body
    assert "No alerts generated yet." in body


def test_dashboard_shows_recent_activity(client) -> None:
    from tests.test_ingestion import build_test_wav_bytes

    wav_payload = build_test_wav_bytes(amplitude=30000)
    client.post(
        "/api/v1/audio/ingestions",
        data={"device_key": "Living Room Phone"},
        files={"audio_file": ("sample.wav", wav_payload, "audio/wav")},
    )

    response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "living-room-phone" in body
    assert "spike_peak" in body
    assert "telegram" in body
