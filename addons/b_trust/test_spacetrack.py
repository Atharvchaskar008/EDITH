import pytest

from spacetrack import RateLimiter, SpaceTrack, credentials


class FakeClock:
    def __init__(self):
        self.now, self.slept = 0.0, []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def test_rate_limiter_holds_the_per_minute_and_per_hour_limits():
    clock = FakeClock()
    limiter = RateLimiter(per_minute=3, per_hour=5, clock=clock, sleep=clock.sleep)
    for _ in range(3):
        limiter.wait()
    assert clock.slept == []  # three at once is allowed
    limiter.wait()
    assert clock.slept == [60.0] and clock.now == 60.0  # the fourth waits a minute
    limiter.wait()
    limiter.wait()  # the sixth must wait until the first is an hour old
    assert clock.now == pytest.approx(3600.0)


class FakeResponse:
    def __init__(self, data, text="ok"):
        self.data, self.text = data, text

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, data):
        self.data, self.posts, self.gets = data, [], []

    def post(self, url, data=None, timeout=None):
        self.posts.append(url)
        return FakeResponse({}, text='""')

    def get(self, url, timeout=None):
        self.gets.append(url)
        return FakeResponse(self.data)


def client(tmp_path, data):
    clock = FakeClock()
    session = FakeSession(data)
    limiter = RateLimiter(clock=clock, sleep=clock.sleep)
    return SpaceTrack(cache_dir=tmp_path, session=session, limiter=limiter, login=("someone", "secret")), session


def test_a_cached_answer_is_never_requested_again(tmp_path):
    records = [{"NORAD_CAT_ID": "5", "EPOCH": "2026-10-02T00:00:00"}, {"NORAD_CAT_ID": "5", "EPOCH": "2026-10-01T00:00:00"}]
    first, session = client(tmp_path, records)
    answer = first.history([5], "2026-10-01", "2026-10-03")
    assert [r["EPOCH"] for r in answer] == ["2026-10-01T00:00:00", "2026-10-02T00:00:00"]  # oldest first
    assert len(session.posts) == 1 and len(session.gets) == 1
    first.history([5], "2026-10-01", "2026-10-03")
    assert len(session.gets) == 1
    second, other_session = client(tmp_path, records)  # a new client finds the same cache
    second.history([5], "2026-10-01", "2026-10-03")
    assert other_session.gets == [] and other_session.posts == []


def test_many_objects_go_in_chunks_of_fifty(tmp_path):
    st, session = client(tmp_path, [])
    st.history(list(range(1, 121)), "2026-10-01", "2026-10-03")
    assert len(session.gets) == 3 and "/NORAD_CAT_ID/1,2,3," in session.gets[0]
    assert all(url.count(",") <= 49 for url in session.gets)


def test_login_is_read_from_a_file_and_missing_login_is_none(tmp_path, monkeypatch):
    monkeypatch.delenv("SPACETRACK_USER", raising=False)
    monkeypatch.delenv("SPACETRACK_PASSWORD", raising=False)
    env = tmp_path / ".env"
    assert credentials([env]) is None
    env.write_text("SPACETRACK_USER=me@example.com\nSPACETRACK_PASSWORD='p=ss'\n")
    assert credentials([env]) == ("me@example.com", "p=ss")
