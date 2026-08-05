from cryptography.fernet import Fernet

from app import db
from app.models.llm import LLMProviderConfig
from app.models.user import User
from app.services.llm.call_logging import LoggedLLMProvider
from app.services.llm.provider_selector import select_provider
from app.services.llm.secrets import encrypt_secret, mask_secret


def test_user_default_provider_is_selected_and_observed(app):
    with app.app_context():
        app.config["LLM_PROVIDER_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
        user = User(username="selection-user", email="selection@example.test", password_hash="x")
        db.session.add(user)
        db.session.flush()
        provider = LLMProviderConfig(
            user_id=user.id,
            name="private",
            base_url="https://llm.example/v1",
            model="private-model",
            api_key_ciphertext=encrypt_secret("private-api-key"),
            api_key_hint=mask_secret("private-api-key"),
            is_enabled=True,
            is_default=True,
        )
        db.session.add(provider)
        db.session.commit()

        selected = select_provider(user.id, operation="qa")

        assert isinstance(selected, LoggedLLMProvider)
        assert selected.provider_config_id == provider.id
        assert selected.model == "private-model"
        assert selected.operation == "qa"
