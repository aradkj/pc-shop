import pytest

from app.core.config import ConfigError, get_settings

STRONG_SECRET = "x" * 48


def test_settings_are_read_from_the_environment(env):
    env.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    env.setenv("CORS_ORIGINS", "http://a.example.com, http://b.example.com ,")
    env.setenv("LOG_LEVEL", "debug")

    settings = get_settings()

    assert settings.access_token_expire_minutes == 15
    assert settings.cors_origins == ("http://a.example.com", "http://b.example.com")
    assert settings.log_level == "DEBUG"
    assert settings.is_production is False


@pytest.mark.parametrize("name", ["DATABASE_URL", "SECRET_KEY"])
def test_required_variables(env, name):
    env.delenv(name)

    with pytest.raises(ConfigError, match=name):
        get_settings()


@pytest.mark.parametrize(
    ("name", "value"),
    [("ACCESS_TOKEN_EXPIRE_MINUTES", "soon"), ("ACCESS_TOKEN_EXPIRE_MINUTES", "0"), ("BCRYPT_ROUNDS", "2")],
)
def test_invalid_numbers_are_rejected(env, name, value):
    env.setenv(name, value)

    with pytest.raises(ConfigError, match=name):
        get_settings()


@pytest.mark.parametrize("secret", ["change-me-to-a-long-random-string", "CHANGE-ME", "too-short"])
def test_production_rejects_weak_secrets(env, secret):
    env.setenv("APP_ENV", "production")
    env.setenv("SECRET_KEY", secret)

    with pytest.raises(ConfigError, match="SECRET_KEY"):
        get_settings()


def test_production_accepts_a_strong_secret(env):
    env.setenv("APP_ENV", "production")
    env.setenv("SECRET_KEY", STRONG_SECRET)

    assert get_settings().is_production is True


def test_development_tolerates_a_placeholder_secret(env):
    env.setenv("APP_ENV", "development")
    env.setenv("SECRET_KEY", "change-me-for-local-use")

    assert get_settings().has_placeholder_secret is True
