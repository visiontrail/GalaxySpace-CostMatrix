"""AI 设置持久化、加密和回退行为测试。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AISettings, Base, User
from app.models.ai_schemas import AIConnectionTestRequest, AISettingsUpdate
from app.services import ai_settings_service


def test_api_key_is_encrypted_and_never_returned(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    session_factory = sessionmaker(bind=test_engine)
    monkeypatch.setattr(ai_settings_service.settings, "anthropic_api_key", "")
    monkeypatch.setattr(ai_settings_service.settings, "secret_key", "unit-test-key")

    with session_factory() as db:
        admin = User(
            username="admin-test",
            password_hash="hash",
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        view = ai_settings_service.save(
            db,
            AISettingsUpdate(
                provider="custom",
                api_key="secret-value",
                base_url="https://models.example.test/anthropic",
                model="test-model",
                max_turns=8,
                max_result_rows=100,
            ),
            admin,
        )
        row = db.query(AISettings).filter(AISettings.id == 1).one()
        effective = ai_settings_service.get_effective(db)

        assert "secret-value" not in row.encrypted_api_key
        assert effective.api_key == "secret-value"
        assert view.api_key_set is True
        assert view.sources["api_key"] == "database"
        assert "secret-value" not in view.model_dump_json()


def test_custom_provider_requires_url_and_model(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    session_factory = sessionmaker(bind=test_engine)
    monkeypatch.setattr(ai_settings_service.settings, "anthropic_api_key", "")

    with session_factory() as db:
        admin = User(username="admin-test", password_hash="hash", is_admin=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)

        try:
            ai_settings_service.save(
                db,
                AISettingsUpdate(
                    provider="custom",
                    base_url="",
                    model="",
                ),
                admin,
            )
        except ValueError as exc:
            assert "Base URL" in str(exc)
        else:
            raise AssertionError("invalid custom provider settings were accepted")


@pytest.mark.parametrize(
    ("provider", "base_url"),
    [
        ("aliyun_beijing", "https://dashscope.aliyuncs.com/apps/anthropic"),
        ("zhipu", "https://open.bigmodel.cn/api/anthropic"),
        ("kimi", "https://api.moonshot.cn/anthropic"),
        ("minimax", "https://api.minimaxi.com/anthropic"),
        ("stepfun_plan", "https://api.stepfun.com/step_plan"),
        ("xiaomi", "https://api.xiaomimimo.com/anthropic"),
        ("tencent", "https://api.hunyuan.cloud.tencent.com/anthropic"),
    ],
)
def test_new_compatible_providers_are_accepted(provider, base_url):
    payload = AISettingsUpdate(
        provider=provider,
        base_url=base_url,
        model="provider-model",
    )
    assert payload.provider == provider


def test_connection_candidate_reuses_saved_api_key(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    session_factory = sessionmaker(bind=test_engine)
    monkeypatch.setattr(ai_settings_service.settings, "anthropic_api_key", "saved-key")

    with session_factory() as db:
        candidate = ai_settings_service.prepare_connection_test(
            db,
            AIConnectionTestRequest(
                provider="kimi",
                base_url="https://api.moonshot.cn/anthropic",
                model="kimi-model",
            ),
        )

    assert candidate.api_key == "saved-key"
    assert candidate.provider == "kimi"


def test_connection_uses_messages_endpoint(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, _):
            return b'{"content":[{"text":"OK"}]}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["api_key"] = request.get_header("X-api-key")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(ai_settings_service, "urlopen", fake_urlopen)
    candidate = ai_settings_service.EffectiveAISettings(
        provider="zhipu",
        api_key="test-key",
        base_url="https://open.bigmodel.cn/api/anthropic",
        model="glm-test",
        max_turns=1,
        request_timeout_seconds=180,
        total_timeout_seconds=1800,
        max_result_rows=10,
        system_prompt="test",
    )

    result = ai_settings_service.test_connection(candidate)

    assert result.success is True
    assert captured == {
        "url": "https://open.bigmodel.cn/api/anthropic/v1/messages",
        "api_key": "test-key",
        "timeout": 30,
    }


def test_primary_and_backup_keys_are_encrypted_independently(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    session_factory = sessionmaker(bind=test_engine)
    monkeypatch.setattr(ai_settings_service.settings, "anthropic_api_key", "")
    monkeypatch.setattr(ai_settings_service.settings, "anthropic_backup_api_key", "")
    monkeypatch.setattr(ai_settings_service.settings, "secret_key", "unit-test-key")

    with session_factory() as db:
        admin = User(username="router-admin", password_hash="hash", is_admin=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        view = ai_settings_service.save(
            db,
            AISettingsUpdate(
                provider="yhroot",
                api_key="yhroot-secret",
                base_url="https://oneapi.yhroot.com",
                model="yinhe-thinking",
                backup_enabled=True,
                backup_provider="kimi",
                backup_api_key="kimi-secret",
                backup_base_url="https://api.moonshot.cn/anthropic",
                backup_model="kimi-k3",
                router_enabled=True,
            ),
            admin,
        )
        row = db.query(AISettings).filter(AISettings.id == 1).one()
        effective = ai_settings_service.get_effective(db)

        assert "yhroot-secret" not in row.encrypted_api_key
        assert "kimi-secret" not in row.encrypted_backup_api_key
        assert effective.api_key == "yhroot-secret"
        assert effective.backup.api_key == "kimi-secret"
        assert view.router_enabled is True
        assert view.backup_api_key_set is True
        assert "yhroot-secret" not in view.model_dump_json()
        assert "kimi-secret" not in view.model_dump_json()
