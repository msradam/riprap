from __future__ import annotations

from app import emissions


def test_empty_base_url_is_local_apple(monkeypatch):
    monkeypatch.delenv("RIPRAP_HARDWARE_LABEL", raising=False)
    monkeypatch.delenv("SPACE_ID", raising=False)
    monkeypatch.delenv("HF_SPACE_ID", raising=False)
    assert emissions.hardware_for("") == "apple_m"


def test_localhost_base_url_is_local_apple(monkeypatch):
    monkeypatch.delenv("RIPRAP_HARDWARE_LABEL", raising=False)
    monkeypatch.delenv("SPACE_ID", raising=False)
    monkeypatch.delenv("HF_SPACE_ID", raising=False)
    assert emissions.hardware_for("http://localhost:8000") == "apple_m"
    assert emissions.hardware_for("http://127.0.0.1:8000") == "apple_m"


def test_remote_hf_space_url_is_l4(monkeypatch):
    monkeypatch.delenv("RIPRAP_HARDWARE_LABEL", raising=False)
    assert emissions.hardware_for("https://msradam-riprap-vllm.hf.space/v1") == "nvidia_l4"


def test_modal_vllm_url_is_a100(monkeypatch):
    monkeypatch.delenv("RIPRAP_HARDWARE_LABEL", raising=False)
    url = "https://msradam-riprap--riprap-vllm-riprap-proxy.modal.run/v1"
    assert emissions.hardware_for(url) == "nvidia_a100"


def test_modal_specialist_url_is_l4(monkeypatch):
    monkeypatch.delenv("RIPRAP_HARDWARE_LABEL", raising=False)
    url = "https://msradam-riprap--riprap-inference-serve.modal.run"
    assert emissions.hardware_for(url) == "nvidia_l4"


def test_hardware_label_override_wins_over_local_url(monkeypatch):
    monkeypatch.setenv("RIPRAP_HARDWARE_LABEL", "NVIDIA L4")
    assert emissions.hardware_for("http://localhost:8000") == "nvidia_l4"


def test_hardware_label_apple_override(monkeypatch):
    monkeypatch.setenv("RIPRAP_HARDWARE_LABEL", "Apple M4 Pro")
    assert emissions.hardware_for("https://msradam-riprap-vllm.hf.space/v1") == "apple_m"


def test_space_id_without_remote_url_is_t4(monkeypatch):
    monkeypatch.delenv("RIPRAP_HARDWARE_LABEL", raising=False)
    monkeypatch.setenv("SPACE_ID", "msradam/riprap")
    assert emissions.hardware_for("") == "nvidia_t4"
