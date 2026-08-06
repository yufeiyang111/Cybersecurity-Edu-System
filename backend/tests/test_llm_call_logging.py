from app import db
from app.models.llm import LLMCallLog
from app.models.user import User
from app.services.llm.call_logging import observe_provider
from app.services.llm.contracts import LLMRequest, LLMResponse, LLMStreamChunk


class _Provider:
    provider_name = "private"
    model = "private-model"
    provider_config_id = 7

    def generate(self, request):
        return LLMResponse(
            text="safe answer",
            provider_name=self.provider_name,
            model=self.model,
            status_code=200,
            usage={"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
        )


class _StreamProvider(_Provider):
    def generate_stream(self, request):
        yield LLMStreamChunk(delta="safe answer")
        yield LLMStreamChunk(
            finished=True,
            usage={
                "prompt_tokens": 22,
                "completion_tokens": 4,
                "total_tokens": 26,
                "prompt_tokens_details": {"cached_tokens": 14},
            },
        )


class _AnthropicStreamProvider(_Provider):
    def generate_stream(self, request):
        yield LLMStreamChunk(delta="safe answer")
        yield LLMStreamChunk(
            finished=True,
            usage={
                "input_tokens": 50,
                "output_tokens": 6,
                "input_token_details": {"cache_read": 30, "cache_creation": 20},
            },
        )


def _user():
    user = User(username="logging-user", email="logging@example.test", password_hash="x")
    db.session.add(user)
    db.session.flush()
    return user


def test_observed_non_stream_call_records_only_usage_metadata(app):
    with app.app_context():
        user = _user()
        observed = observe_provider(_Provider(), user_id=user.id, operation="qa")

        response = observed.generate(LLMRequest(prompt="prompt must not be stored"))

        assert response.is_success
        log = LLMCallLog.query.filter_by(user_id=user.id).one()
        assert log.status == "success"
        assert log.total_tokens == 14
        assert log.input_tokens == 10
        assert log.output_tokens == 4
        assert log.operation == "qa"
        assert log.provider_config_id == 7
        assert "prompt must not be stored" not in repr(log.to_dict())


def test_observed_stream_call_records_usage_and_cached_tokens(app):
    with app.app_context():
        user = _user()
        observed = observe_provider(_StreamProvider(), user_id=user.id, operation="qa")

        chunks = list(observed.generate_stream(LLMRequest(prompt="safe prompt")))

        assert chunks[-1].finished is True
        log = LLMCallLog.query.filter_by(user_id=user.id).one()
        assert log.status == "success"
        assert log.streaming is True
        assert log.input_tokens == 22
        assert log.cached_input_tokens == 14
        assert log.cache_status == "hit"
        assert log.cache_write_input_tokens == 0
        assert log.output_tokens == 4
        assert log.total_tokens == 26


def test_observed_stream_call_normalizes_anthropic_style_usage(app):
    with app.app_context():
        user = _user()
        observed = observe_provider(_AnthropicStreamProvider(), user_id=user.id, operation="qa")

        list(observed.generate_stream(LLMRequest(prompt="safe prompt")))

        log = LLMCallLog.query.filter_by(user_id=user.id).one()
        assert log.input_tokens == 50
        assert log.cached_input_tokens == 30
        assert log.cache_write_input_tokens == 20
        assert log.cache_status == "hit"
