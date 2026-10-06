from src import notifier


def test_writes_outbox_and_prints(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(notifier, "OUTBOX", tmp_path)
    assert notifier.send_to_admin("hello admin", 7) == "console"
    assert (tmp_path / "request_7.txt").read_text(encoding="utf-8") == "hello admin"
    assert "hello admin" in capsys.readouterr().out


def test_creates_outbox_dir_and_overwrites_per_reservation(tmp_path, monkeypatch):
    target = tmp_path / "nested"
    monkeypatch.setattr(notifier, "OUTBOX", target)
    notifier.send_to_admin("first", 1)
    notifier.send_to_admin("second", 1)
    assert (target / "request_1.txt").read_text(encoding="utf-8") == "second"